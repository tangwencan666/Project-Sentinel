import asyncio
import hashlib
import json
import os
if os.getenv('PUBLIC_DEMO_MODE','false').lower() in ('true','1','yes'):
    raise RuntimeError('Public mode must use sentinel.public_demo:create_app; live runtime import refused')
import uuid
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import StreamingResponse
from typing import Literal
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb
from services.runtime import pool, audit_pool, redis, query
from .scenarios import SCENARIOS, REGISTRY
from .evidence import summary, metrics, logs, kafka, traces, database, cache
from .agent import investigate, step
from .patching import validate, BASE, propose
from .storage import migrate,usage,event
from .security import install_masking,serial
from .provider import status as provider_status,complete,ProviderError

tasks=set()
running=set()
last_good=[]
LIVE_ENABLED=os.getenv('LIVE_AI_ENABLED','false').lower() in ('true','1','yes')

def background(coroutine):
    task=asyncio.create_task(coroutine)
    tasks.add(task); task.add_done_callback(tasks.discard)
    return task

async def run_investigation(incident_id,mode='HYBRID_V2',resume_run_id=None):
    if not LIVE_ENABLED: raise RuntimeError('Live AI is disabled; set LIVE_AI_ENABLED=true locally')
    if incident_id in running: return
    running.add(incident_id)
    try:
        if mode in ('HYBRID_V3_1','HYBRID_V3_1_1','HYBRID_V3_1_2','HYBRID_V3_1_3','HYBRID_V3_1_4','HYBRID_V4','HYBRID_V4_1'):
            from .runtime_agent import investigate_runtime
            await investigate_runtime(incident_id,mode,resume_run_id)
        elif mode in ('HYBRID_V2','HYBRID_V3'):
            from .hybrid import investigate_hybrid
            await investigate_hybrid(incident_id,mode,resume_run_id)
        else: await investigate(incident_id,mode)
    finally: running.discard(incident_id)

async def new_incident(signal,mode='HYBRID_V2',controlled_recovery=False):
    incident_id=str(uuid.uuid4())
    await query('INSERT INTO incidents(id,status,signal,baseline,controlled_recovery) VALUES(%s,%s,%s,%s,%s)',(incident_id,'detected',Jsonb(signal),Jsonb(json.loads(json.dumps(last_good,default=str))),controlled_recovery))
    background(run_investigation(incident_id,mode))
    return incident_id

async def detector():
    global last_good
    while True:
        try:
            if await redis.exists('control:evaluation_lock'):
                await asyncio.sleep(3)
                continue
            rows=await summary(20)
            signals=[dict(row) for row in rows if row['requests']>=5 and (float(row['error_pct'])>10 or row['p95_ms']>1000)]
            queue=await kafka()
            lag=sum(p['lag'] for p in queue)
            if lag>20: signals.append({'service':'notification-service','consumer_lag':lag})
            # Query amplification: detect above a measured healthy baseline, not the injection registry.
            measured=await metrics()
            db_rates=measured['db_qps'].get('data',{}).get('result',[])
            for item in db_rates:
                if item['metric'].get('service')=='inventory-service' and float(item['value'][1])>5:
                    signals.append({'service':'inventory-service','db_qps':float(item['value'][1]),'threshold':5})
            if signals:
                active=await query("SELECT id FROM incidents WHERE created_at>now()-interval '90 seconds' LIMIT 1",one=True)
                if not active: await new_incident(json.loads(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'signals':signals},default=str)))
            else: last_good=rows
        except asyncio.CancelledError: raise
        except Exception as exc:
            print(json.dumps({'detector_error':str(exc)}),flush=True)
        await asyncio.sleep(8)

@asynccontextmanager
async def lifespan(app):
    await pool.open(); await audit_pool.open()
    await pool.wait(timeout=30); await audit_pool.wait(timeout=30)
    install_masking()
    await migrate()
    pending=await query("SELECT r.id,r.incident_id,r.mode FROM investigation_runs r JOIN investigation_checkpoints c ON c.run_id=r.id WHERE r.status='started' AND r.mode IN ('HYBRID_V2','HYBRID_V3','HYBRID_V4_1') AND c.phase!='COMPLETED'")
    await query("UPDATE incidents SET status='interrupted' WHERE status IN ('investigating','detected') AND mode NOT IN ('HYBRID_V2','HYBRID_V3','HYBRID_V4_1')")
    await query("UPDATE investigation_runs SET status='interrupted',finished_at=now() WHERE status='started' AND mode NOT IN ('HYBRID_V2','HYBRID_V3','HYBRID_V4_1')")
    await query("UPDATE tool_calls SET status='interrupted',finished_at=now() WHERE status='started'")
    await query("UPDATE llm_calls SET status='interrupted',finished_at=now() WHERE status='started'")
    if LIVE_ENABLED:
        for row in pending: background(run_investigation(str(row['incident_id']),row['mode'],str(row['id'])))
        background(detector())
    yield
    for task in list(tasks): task.cancel()
    await asyncio.gather(*tasks,return_exceptions=True)
    await pool.close(); await audit_pool.close(); await redis.aclose()

app=FastAPI(title='Project Sentinel control plane',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','sentinel'])

@app.middleware('http')
async def protect_mutations(request: Request,call_next):
    if 'range' in request.headers:
        return PlainTextResponse('Byte-range requests are not supported.',status_code=416)
    if not LIVE_ENABLED and request.method not in ('GET','HEAD','OPTIONS'):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Live AI is disabled. Enable LIVE_AI_ENABLED=true locally to use controls.'},status_code=403)
    # Local-only demo; browsers must send same-origin mutations. No permissive CORS.
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'cross-origin mutation rejected'},status_code=403)
    return await call_next(request)

@app.get('/health')
async def health(): return {'status':'healthy'}

@app.get('/api/overview')
async def overview():
    provider=provider_status()
    return {'services':await summary(30),'traffic_enabled':await redis.get('traffic:enabled')!='0','model':{'configured':provider['configured'],'name':provider['model']},'provider':provider,'active_faults':[s['scenario_id'] for s in SCENARIOS if await redis.exists('fault:'+s['scenario_id'])],'time':datetime.now(timezone.utc).isoformat()}

@app.get('/api/scenarios')
async def scenarios():
    return [{k:v for k,v in s.items() if k not in ('ground_truth_root_cause','expected_evidence','recovery_method')} for s in SCENARIOS]

class Trigger(BaseModel):
    duration_seconds:int=Field(default=120,ge=10,le=600)

@app.post('/api/faults/{scenario_id}')
async def trigger(scenario_id:str,body:Trigger):
    if scenario_id not in REGISTRY: raise HTTPException(404)
    await redis.set('fault:'+scenario_id,'1',ex=body.duration_seconds)
    return {'active':scenario_id,'expires_in':body.duration_seconds}

@app.delete('/api/faults/{scenario_id}')
async def stop(scenario_id:str):
    if scenario_id not in REGISTRY: raise HTTPException(404)
    await redis.delete('fault:'+scenario_id)
    return {'stopped':scenario_id}

@app.post('/api/recover')
async def recover():
    await redis.delete(*['fault:'+s['scenario_id'] for s in SCENARIOS])
    return {'status':'injection_stopped','note':'In-flight requests and queue backlog may require time to drain. This is not a code patch.'}

@app.post('/api/traffic/{enabled}')
async def traffic(enabled:bool):
    await redis.set('traffic:enabled','1' if enabled else '0')
    return {'enabled':enabled}

@app.get('/api/incidents')
async def incidents(): return await query("SELECT * FROM incidents WHERE status!='test' ORDER BY created_at DESC LIMIT 50")

@app.get('/api/incidents/{incident_id}')
async def incident(incident_id:uuid.UUID):
    row=await query('SELECT * FROM incidents WHERE id=%s',(incident_id,),one=True)
    if not row: raise HTTPException(404)
    row['steps']=await query('SELECT * FROM agent_steps WHERE incident_id=%s ORDER BY id',(incident_id,))
    return row

class InvestigationMode(BaseModel):
    mode:Literal['AI','RULE_BASED','HYBRID_V2','HYBRID_V3','HYBRID_V3_1','HYBRID_V3_1_1','HYBRID_V3_1_2','HYBRID_V3_1_3','HYBRID_V3_1_4','HYBRID_V4','HYBRID_V4_1']='HYBRID_V2'
    controlled_recovery:bool=False

@app.post('/api/incidents')
async def manual_incident(body:InvestigationMode=InvestigationMode()):
    if body.mode in ('HYBRID_V3_1','HYBRID_V3_1_1','HYBRID_V3_1_2','HYBRID_V3_1_3','HYBRID_V3_1_4','HYBRID_V4'): raise HTTPException(409,'V3.1 is archived. Use HYBRID_V4_1 for new work or the frozen phase4-v3.1-first image for exact reproduction.')
    return {'id':await new_incident(json.loads(json.dumps({'signals':await summary(),'source':'operator_requested'},default=str)),body.mode,body.controlled_recovery)}

@app.post('/api/incidents/{incident_id}/investigate')
async def retry(incident_id:uuid.UUID,body:InvestigationMode=InvestigationMode()):
    if body.mode in ('HYBRID_V3_1','HYBRID_V3_1_1','HYBRID_V3_1_2','HYBRID_V3_1_3','HYBRID_V3_1_4','HYBRID_V4'): raise HTTPException(409,'V3.1 is archived; use a current runtime version for new work.')
    row=await query('SELECT id FROM incidents WHERE id=%s',(incident_id,),one=True)
    if not row: raise HTTPException(404)
    if str(incident_id) in running: raise HTTPException(409,'investigation already running')
    await query('UPDATE incidents SET controlled_recovery=%s WHERE id=%s',(body.controlled_recovery,incident_id))
    background(run_investigation(str(incident_id),body.mode))
    return {'status':'scheduled'}

class RecoveryMeasurement(BaseModel):
    run_id:uuid.UUID

@app.post('/api/incidents/{incident_id}/recovery-measurement')
async def recovery_measurement(incident_id:uuid.UUID,body:RecoveryMeasurement):
    from .recovery import capture_after
    try: return await capture_after(incident_id,body.run_id)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc

@app.get('/api/evidence/{kind}')
async def evidence(kind:str):
    fn={'metrics':metrics,'logs':logs,'traces':traces,'database':database,'cache':cache,'queue':kafka}.get(kind)
    if not fn: raise HTTPException(404)
    return await fn()

@app.post('/api/incidents/{incident_id}/resume')
async def resume(incident_id:uuid.UUID):
    row=await incident(incident_id)
    if row['mode'] in ('HYBRID_V3_1','HYBRID_V3_1_1','HYBRID_V3_1_2','HYBRID_V3_1_3','HYBRID_V3_1_4','HYBRID_V4'): raise HTTPException(409,'Frozen V3.1 first-run records cannot be resumed with a different runtime revision.')
    if row['mode'] not in ('HYBRID_V2','HYBRID_V3','HYBRID_V3_1_1','HYBRID_V3_1_2','HYBRID_V3_1_3','HYBRID_V3_1_4','HYBRID_V4','HYBRID_V4_1'): raise HTTPException(409,'This version does not support checkpoint resume')
    if str(incident_id) in running: raise HTTPException(409,'investigation already running')
    checkpoint=await query('SELECT phase,payload FROM investigation_checkpoints WHERE run_id=%s',(row['investigation_run'],),one=True)
    if not checkpoint or checkpoint['phase']=='COMPLETED': raise HTTPException(409,'no resumable checkpoint')
    if checkpoint['payload'].get('resume_count',0)>=3: raise HTTPException(409,'resume budget exhausted')
    background(run_investigation(str(incident_id),row['mode'],str(row['investigation_run'])))
    return {'status':'resume_scheduled','run_id':str(row['investigation_run']),'phase':checkpoint['phase']}

@app.get('/api/incidents/{incident_id}/report',response_class=PlainTextResponse)
async def report(incident_id:uuid.UUID):
    data=await incident(incident_id)
    analysis=data.get('report') or {}
    lines=[f'# Sentinel Incident {incident_id}',f'\nCreated: {data["created_at"]}  \nStatus: {data["status"]}  \nMode: {data.get("mode")}  \nModel: {analysis.get("model") or "N/A"}', '\n## Analysis',str(analysis.get('summary','No final report was generated; raw failed-attempt events are retained below.')), '\n## Root cause proposal',str(analysis.get('root_cause','Not established.'))]
    diagnosis=analysis.get('diagnosis') or {}
    if diagnosis:
        lines += ['\n## Evidence references',', '.join(diagnosis.get('evidence_ids',[])),'\n## Recommended action',diagnosis.get('patch_decision','Unknown')+': '+diagnosis.get('recommended_fix',''),'\n## Remaining uncertainty','\n'.join('- '+u for u in diagnosis.get('remaining_uncertainty',[]))]
    review=analysis.get('critic')
    if review: lines += ['\n## Critic: '+review['verdict'],review['verification_summary'],'\nTest sufficiency: '+review['test_sufficiency']]
    candidate=analysis.get('patch')
    if candidate: lines += ['\n## Candidate patch: '+candidate.get('origin','Unknown'),'Status: '+candidate.get('status','Unknown')+'; production deployment is separate.','```diff',candidate.get('submitted_diff',candidate.get('diff','')),'```']
    measured=analysis.get('measured_recovery') or (candidate or {}).get('replay')
    if measured:
        lines += ['\n## Measured before / after','Scope: operator recovery (not an AI repair).' if measured.get('not_an_ai_repair') else 'Scope: sandbox pricing HTTP replay with live inventory.','| Window | Service | Requests | Error % | P50 ms | P95 ms | P99 ms | RPS |','|---|---|---:|---:|---:|---:|---:|---:|']
        for window in ('before','after'):
            snapshot=measured.get(window) or {}
            for row in snapshot.get('http',[snapshot] if snapshot.get('requests') is not None else []):
                lines.append('| '+window+' | '+row.get('service','sandbox')+' | '+' | '.join(str(row.get(k,'Unknown')) for k in ('requests','error_pct','p50_ms','p95_ms','p99_ms','throughput_rps'))+' |')
    lines+=['\n## Evidence and audit','| Step | Time | Kind | Actor / Tool |','|---|---|---|---|']
    for s in data['steps']:
        actor=s['payload'].get('agent') or s['payload'].get('actor','platform')
        lines.append(f'| {s["id"]} | {s["ts"]} | {s["kind"]} | {actor} / {s["payload"].get("tool",s["payload"].get("name", ""))} |')
    if data.get('verification'):
        lines+=['\n## Before / after','| Window | Service | Requests | Error % | p95 ms |','|---|---|---:|---:|---:|']
        for window in ('before','after'):
            for row in data['verification'].get(window,[]):
                lines.append(f'| {window} | {row["service"]} | {row["requests"]} | {row["error_pct"]} | {round(row["p95_ms"],2)} |')
    lines+=['\n## Complete raw record','```json',json.dumps(data,ensure_ascii=False,indent=2,default=str),'```']
    return '\n'.join(lines)+'\n'

class Deployment(BaseModel):
    sha256:str=Field(pattern='^[a-f0-9]{64}$')

class OperatorPatch(BaseModel):
    source:str=Field(max_length=8000)

@app.post('/api/incidents/{incident_id}/patch')
async def operator_patch(incident_id:uuid.UUID,body:OperatorPatch):
    await incident(incident_id)
    try:
        result=await asyncio.to_thread(propose,body.source,str(incident_id))
    except (ValueError,SyntaxError) as exc:
        raise HTTPException(422,str(exc)) from exc
    result['origin']='HUMAN'
    await step(incident_id,'tool_result',{'name':'propose_patch','actor':'operator','origin':'HUMAN','result':result})
    return result

@app.post('/api/incidents/{incident_id}/deploy')
async def deploy(incident_id:uuid.UUID,body:Deployment):
    data=await incident(incident_id)
    candidates=[s['payload']['result'] for s in data['steps'] if s['kind']=='tool_result' and s['payload'].get('name')=='propose_patch' and s['payload'].get('result',{}).get('sha256')==body.sha256]
    ai=await query('SELECT artifact FROM ai_patches WHERE incident_id=%s AND run_id=%s ORDER BY created_at DESC',(incident_id,data.get('investigation_run')))
    matching=[row['artifact'] for row in ai if row['artifact'].get('sha256')==body.sha256]
    if matching:
        if matching[0].get('profile'):
            raise HTTPException(409,'Generic candidates require source review and a separate release; they cannot use the live pricing overlay.')
        if not matching[0].get('candidate_verified') or ((data.get('report') or {}).get('critic') or {}).get('verdict')!='VERIFIED': raise HTTPException(409,'AI candidate requires replay and Critic VERIFIED')
        candidates=matching
    if not candidates or not candidates[-1].get('validated'): raise HTTPException(409,'No validated patch for this incident')
    patch=candidates[-1]
    if hashlib.sha256(BASE.read_bytes()).hexdigest()!=patch['base_sha256']: raise HTTPException(409,'Base source changed')
    if validate(patch['source'])!=body.sha256: raise HTTPException(409,'Patch digest mismatch')
    if not await redis.set('repair:deployment_lock',str(incident_id),nx=True,ex=60): raise HTTPException(409,'Another deployment is being verified')
    before=await summary(20)
    await redis.set('repair:pricing',patch['source'])
    await redis.set('repair:incident',str(incident_id))
    await step(incident_id,'deployment',{'sha256':body.sha256,'target':'order-service pricing function','before':json.loads(json.dumps(before,default=str))})
    await query("UPDATE incidents SET status='verifying' WHERE id=%s",(incident_id,))
    background(verify(incident_id,before))
    return {'status':'verifying','window_seconds':35}

async def verify(incident_id,before):
    await asyncio.sleep(35)
    after=await summary(25)
    relevant=[r for r in after if r['service']=='order-service']
    verified=bool(relevant and relevant[0]['requests']>=10 and float(relevant[0]['error_pct'])==0)
    # The reproducer must still be active; otherwise recovery cannot be attributed to this patch.
    reproducer_active=bool(await redis.exists('fault:code_exception'))
    verified=verified and reproducer_active
    result=json.loads(json.dumps({'before':before,'after':after,'verified':verified,'reproducer_active':reproducer_active,'criterion':'at least 10 order requests, zero errors, original reproducer remains enabled'},default=str))
    await query('UPDATE incidents SET status=%s,verification=%s WHERE id=%s',('resolved' if verified else 'verification_failed',Jsonb(result),incident_id))
    await step(incident_id,'verification',result)
    await redis.delete('repair:deployment_lock')

@app.post('/api/rollback')
async def rollback():
    incident_id=await redis.get('repair:incident')
    await redis.delete('repair:pricing')
    await redis.delete('repair:incident')
    if incident_id:
        await step(incident_id,'rollback',{'actor':'operator','target':'order-service pricing','status':'original_source_restored'})
        await query("UPDATE incidents SET status='rolled_back' WHERE id=%s",(incident_id,))
    return {'status':'original_pricing_restored'}

@app.get('/api/provider')
async def provider_info(): return {**provider_status(),'usage':await usage(include_calls=False)}

@app.post('/api/provider/check')
async def provider_check():
    try:
        await complete(None,None,'ProviderCheck',[{'role':'user','content':'Return only the word OK.'}])
        return provider_status()
    except ProviderError as exc:
        return {'status':'unavailable','error':exc.public(),'configured':provider_status()['configured']}

@app.get('/api/incidents/{incident_id}/agent')
async def agent_detail(incident_id:uuid.UUID):
    data=await incident(incident_id)
    run_id=data.get('investigation_run')
    return serial({'mode':data.get('mode'),'run_id':run_id,'provider':provider_status(),'usage':await usage(incident_id),'tool_calls':await query('SELECT * FROM tool_calls WHERE incident_id=%s ORDER BY started_at',(incident_id,)),'evidence':await query('SELECT * FROM evidence_items WHERE incident_id=%s ORDER BY collected_at',(incident_id,)),'hypotheses':await query('SELECT * FROM hypotheses WHERE incident_id=%s ORDER BY updated_at',(incident_id,)),'patches':await query('SELECT * FROM ai_patches WHERE incident_id=%s ORDER BY created_at',(incident_id,)),'runs':await query('SELECT * FROM investigation_runs WHERE incident_id=%s ORDER BY started_at',(incident_id,))})

@app.get('/api/incidents/{incident_id}/events')
async def stream_events(incident_id:uuid.UUID,request:Request,after:int=0):
    await incident(incident_id)
    try: cursor=max(after,int(request.headers.get('last-event-id','0')))
    except ValueError: raise HTTPException(400,'Invalid event cursor')
    async def stream():
        nonlocal cursor
        while not await request.is_disconnected():
            rows=await query('SELECT * FROM agent_steps WHERE incident_id=%s AND id>%s ORDER BY id LIMIT 100',(incident_id,cursor))
            for row in rows:
                cursor=row['id']
                yield f'id: {cursor}\nevent: investigation\ndata: '+json.dumps(serial(row),ensure_ascii=False)+'\n\n'
            if not rows: yield ': heartbeat\n\n'
            await asyncio.sleep(.5)
    return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.post('/api/evaluation-session/{enabled}')
async def evaluation_session(enabled:bool):
    if enabled: await redis.set('control:evaluation_lock','1',ex=7200)
    else: await redis.delete('control:evaluation_lock')
    return {'automatic_detector_paused':enabled,'reason':'serial controlled evaluation; manual incidents still available'}

class EvaluationRequest(BaseModel):
    scenario_id:str

@app.post('/api/incidents/{incident_id}/evaluate')
async def score_incident(incident_id:uuid.UUID,body:EvaluationRequest):
    from .evaluator import evaluate
    try: return await evaluate(incident_id,body.scenario_id)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc

@app.get('/api/evaluations')
async def evaluation_results():
    return await query('SELECT * FROM evaluations ORDER BY created_at DESC LIMIT 100')

@app.get('/api/measured')
async def measured_snapshot():
    from .tool_registry import health
    return serial({'source':'Measured','observed_at':datetime.now(timezone.utc).isoformat(),'window_seconds':20,'http':await summary(20),'db_pool':await health(),'kafka_lag':await kafka()})

@app.get('/api/comparison')
async def comparison():
    path=Path('/app/evaluation/phase4/comparison.json')
    if not path.exists(): path=Path('/app/evaluation/comparison.json')
    if not path.exists(): return {'status':'pending','versions':[],'message':'Real evaluations have not been published yet.'}
    return json.loads(path.read_text(encoding='utf-8'))

@app.get('/api/recorded-runs/{run_id}')
async def recorded_run(run_id:uuid.UUID):
    path=Path('/app/evaluation/runs')/(str(run_id)+'.json')
    if not path.exists(): raise HTTPException(404,'recorded artifact not available')
    return {'display_mode':'RECORDED RUN','live':False,**json.loads(path.read_text(encoding='utf-8'))}

@app.get('/api/incidents/{incident_id}/context')
async def context_metrics(incident_id:uuid.UUID):
    data=await incident(incident_id)
    return serial({'estimated':True,'estimate_method':'characters / 4',
        'measurements':await query('SELECT * FROM context_measurements WHERE run_id=%s ORDER BY id',(data['investigation_run'],)),
        'checkpoint':await query('SELECT phase,updated_at FROM investigation_checkpoints WHERE run_id=%s',(data['investigation_run'],),one=True)})

@app.get('/api/incidents/{incident_id}/runtime')
async def runtime_diagnostics(incident_id:uuid.UUID):
    from .diagnostics import project
    row=await query('SELECT investigation_run,mode,status FROM incidents WHERE id=%s',(incident_id,),one=True)
    if not row: raise HTTPException(404)
    rid=row['investigation_run']
    checkpoint=await query('SELECT phase,updated_at,payload FROM investigation_checkpoints WHERE run_id=%s',(rid,),one=True)
    measures=await query('SELECT * FROM context_measurements WHERE run_id=%s ORDER BY id DESC LIMIT 30',(rid,))
    calls=await query('SELECT id,agent,status,started_at,finished_at,input_tokens,output_tokens,total_tokens,error,diagnostics FROM llm_calls WHERE run_id=%s ORDER BY started_at DESC LIMIT 30',(rid,))
    counts=await query("SELECT kind,count(*) AS count FROM agent_steps WHERE incident_id=%s AND payload->>'run_id'=%s GROUP BY kind ORDER BY kind",(incident_id,str(rid)))
    return {**project(checkpoint,measures,calls,counts),'run_id':str(rid) if rid else None,'mode':row['mode'],'status':row['status']}

@app.get('/api/incidents/{incident_id}/patches/{patch_id}.diff',response_class=PlainTextResponse)
async def export_patch(incident_id:uuid.UUID,patch_id:uuid.UUID):
    row=await query('SELECT artifact FROM ai_patches WHERE id=%s AND incident_id=%s',(patch_id,incident_id),one=True)
    if not row: raise HTTPException(404)
    return PlainTextResponse(row['artifact'].get('submitted_diff',row['artifact'].get('diff','')),
        headers={'Content-Disposition':f'attachment; filename="sentinel-candidate-{patch_id}.diff"'},media_type='text/x-diff')

@app.get('/api/release-evaluation')
async def release_evaluation():
    path=Path('/app/evaluation/phase4/final-release-report.json')
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'status':'pending','message':'Final release benchmark has not completed; historical results remain in comparison.'}

from .public_demo import router as portfolio_router
from fastapi.responses import FileResponse
app.include_router(portfolio_router)
for page_name in ('incident','replay','evidence','root-cause','patch','evaluation','architecture','documentation'):
    app.add_api_route('/'+page_name+'.html',lambda:FileResponse('/app/web/index.html'),methods=['GET'])
app.mount('/',StaticFiles(directory='/app/web',html=True),name='dashboard')
