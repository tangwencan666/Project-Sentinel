"""The only Investigator capability interface. No registry/control-plane traversal."""
import asyncio
import json
from pathlib import Path
import uuid
import httpx
from pydantic import Field
from psycopg.types.json import Jsonb
from services.runtime import query
from . import evidence as adapters
from .contracts import Strict,Hypothesis,Diagnosis,Critique,check_citations,validate_diagnosis
from .storage import event,evidence_for
from .security import serial

SOURCE_FILES={'services/pricing.py','services/runtime.py','services/checkout.py','services/background.py','tests/pricing_contract.py','services/payment.py','services/order.py','services/inventory.py'}
ROOT=Path('/app')
CUSTOM_HANDLERS={}

class Empty(Strict): pass
class Service(Strict): service:str|None=Field(default=None,max_length=50)
class Logs(Service): severity:str|None=Field(default=None,pattern='^(ERROR|INFO)$')
class Trace(Strict): trace_id:str|None=Field(default=None,pattern=r'^[0-9a-f]{32}$')
class Search(Strict): text:str=Field(min_length=1,max_length=100)
class Read(Strict):
    path:str
    start_line:int=Field(default=1,ge=1)
    end_line:int=Field(default=160,ge=1,le=500)
class Diff(Strict): diff:str=Field(min_length=10,max_length=16000)
class GenericDiff(Diff): path:str
class EvidenceRead(Strict):
    evidence_id:str=Field(pattern=r'^E-[0-9a-f]{16}$')
    offset:int=Field(default=0,ge=0)
    length:int=Field(default=4000,ge=100,le=5000)

DEFINITIONS={
 'search_logs':(Logs,'Read real HTTP logs from this incident time window; filter service and ERROR/INFO severity, at most 60 samples.'),
 'query_metrics':(Empty,'Read Prometheus rates and measured p50/p95/p99/throughput from HTTP observations.'),
 'get_trace':(Trace,'Read completed real distributed traces. trace_id may come from logs.'),
 'get_service_health':(Service,'Read live service health and actual connection pool stats.'),
 'search_repository':(Search,'Literal search of allowlisted source; fault harness, configuration, reports, and truth are inaccessible.'),
 'read_source_file':(Read,'Read real numbered lines from allowlisted business source: services/pricing.py, services/payment.py, services/order.py, services/inventory.py, services/runtime.py, tests/pricing_contract.py.'),
 'inspect_database':(Empty,'Read active sessions plus two pg_stat_statements snapshots and their measured deltas.'),
 'inspect_redis':(Empty,'Read catalog TTL and cumulative Redis statistics.'),
 'inspect_kafka':(Empty,'Read committed/end offsets and lag for notification consumer.'),
 'read_evidence':(EvidenceRead,'Read a stored observation from this investigation only, in bounded character pages. Use after preview/context truncation; next_offset is null at the end.'),
 'record_hypothesis':(Hypothesis,'Create, update or reject a hypothesis using real evidence IDs and a concise user-facing summary, never hidden reasoning.'),
 'complete_investigation':(Diagnosis,'Submit the final structured diagnosis with evidence IDs, after recording a hypothesis. Use this tool instead of prose.'),
 'submit_verification':(Critique,'Submit the independent Critic verdict with concise bounded fields and real evidence citations.'),
 'generate_diff':(Diff,'Parse and validate a unified diff in memory without applying to the main tree.'),
 'validate_patch':(Diff,'Apply unified diff only in a sandbox copy, run immutable unit tests, HTTP integration tests, fault replay and measured before/after.'),
 'run_tests':(Diff,'Run the same guarded sandbox test and replay pipeline for a proposed unified diff.'),
 'validate_generic_patch':(GenericDiff,'Trusted TestAgent capability: validate a path-selected pure business candidate in isolated services and real scoped dependencies. Never applies production changes.'),
}
TOOLS=[{'type':'function','function':{'name':name,'description':desc,'parameters':schema.model_json_schema()}} for name,(schema,desc) in DEFINITIONS.items() if name!='validate_generic_patch']

def read_source(path,start_line=1,end_line=160):
    if path not in SOURCE_FILES: raise ValueError('source path not allowlisted')
    file=ROOT/path
    if file.is_symlink() or not file.resolve().is_relative_to(ROOT.resolve()): raise ValueError('source traversal rejected')
    lines=file.read_text().splitlines();end=min(end_line,len(lines))
    if start_line>end: raise ValueError('empty source range')
    return {'path':path,'start_line':start_line,'end_line':end,'source':'\n'.join(f'{n}: {lines[n-1]}' for n in range(start_line,end+1))}

def statement_deltas(before,after):
    def identity(row): return (row['userid'],row['dbid'],row['queryid'])
    counts={identity(s):s['calls'] for s in before}
    return [{'userid':s['userid'],'dbid':s['dbid'],'queryid':s['queryid'],'query':s['query'],'calls_delta':s['calls']-counts[identity(s)] if identity(s) in counts and s['calls']>=counts[identity(s)] else None} for s in after]

async def health(service=None):
    names=[service] if service else adapters.SERVICES
    if any(name not in adapters.SERVICES for name in names): raise ValueError('unknown service')
    async with httpx.AsyncClient(timeout=3) as client:
        result=[]
        for name in names:
            entry={'service':name,'source':'Measured'}
            for endpoint in ('health','pool-stats'):
                try:
                    response=await client.get(f'http://{name}:8000/{endpoint}')
                    entry[endpoint]={'http_status':response.status_code,'body':response.json()}
                except Exception: entry[endpoint]={'status':'unavailable'}
            result.append(entry)
        return result

async def invoke(name,args,incident_id,run_id):
    if name=='validate_generic_patch':
        from .generic_patching import parse_diff,validate_candidate
        run=await query('SELECT mode FROM investigation_runs WHERE id=%s',(run_id,),one=True)
        origin='TEST_FIXTURE' if run and run['mode'] in ('RELIABILITY_TEST','TEST') else 'AI_GENERATED'
        key=args.get('_execution_key')
        if key:
            saved=await query("SELECT artifact FROM ai_patches WHERE run_id=%s AND artifact->>'execution_key'=%s ORDER BY created_at LIMIT 1",(run_id,key),one=True)
            if saved: return saved['artifact']
        path=args['path']
        try:
            parsed,_,_,_=parse_diff(args['diff'])
            if parsed!=path: raise ValueError('Proposed path differs from eligibility-selected path')
            result=await validate_candidate(args['diff'],incident_id,origin=origin)
        except (ValueError,SyntaxError) as exc:
            result={'origin':origin,'path':path,'profile':'blocked','submitted_diff':args['diff'],
                'candidate_verified':False,'production_applied':False,'automatic_apply_allowed':False,
                'status':'STATIC_POLICY_REJECTED','error':{'code':'PATCH_POLICY_DENIED','message':str(exc)}}
        result['execution_key']=key
        pid=str(uuid.uuid4());result['patch_id']=pid
        await query('INSERT INTO ai_patches(id,incident_id,run_id,origin,status,artifact) VALUES(%s,%s,%s,%s,%s,%s)',
            (pid,incident_id,run_id,origin,result['status'],Jsonb(serial(result))))
        await event(incident_id,result['status'],{'patch_id':pid,'path':path,'origin':origin,'risk':result.get('risk'),
            'tests':result.get('candidate_test'),'error':result.get('error'),'replay':result.get('replay'),'automatic_apply_allowed':False},'TestAgent',run_id)
        return result
    if name in ('inspect_database','inspect_redis','inspect_kafka'):
        run=await query('SELECT mode FROM investigation_runs WHERE id=%s',(run_id,),one=True)
        if run and run['mode'] in ('HYBRID_V4','HYBRID_V4_1'):
            from .infra_observations import postgres_observation,redis_observation,kafka_observation
            return await {'inspect_database':postgres_observation,'inspect_redis':redis_observation,'inspect_kafka':kafka_observation}[name]()
    if name in CUSTOM_HANDLERS: return await CUSTOM_HANDLERS[name](name,args,incident_id,run_id)
    if name=='submit_verification':
        result=Critique.model_validate(args)
        check_citations(result.evidence_ids,await evidence_for(incident_id,run_id),2)
        return {'critique':result.model_dump()}
    if name=='read_evidence':
        item=await query('SELECT payload FROM evidence_items WHERE id=%s AND incident_id=%s AND run_id=%s',(args['evidence_id'],incident_id,run_id),one=True)
        if not item: raise ValueError('unknown evidence in this investigation')
        text=json.dumps(item['payload'],ensure_ascii=False,default=str)
        end=args['offset']+args['length']
        return {'evidence_id':args['evidence_id'],'text':text[args['offset']:end],'next_offset':end if end<len(text) else None,'total_characters':len(text)}
    if name=='complete_investigation':
        diagnosis=validate_diagnosis(args,await evidence_for(incident_id,run_id))
        if not await query('SELECT id FROM hypotheses WHERE run_id=%s',(run_id,)): raise ValueError('record a hypothesis first')
        return {'diagnosis':diagnosis.model_dump()}
    if name=='search_logs':
        if args['service'] and args['service'] not in adapters.SERVICES: raise ValueError('unknown service')
        incident=await query('SELECT created_at FROM incidents WHERE id=%s',(incident_id,),one=True)
        return await adapters.sql("SELECT * FROM request_logs WHERE ts>=%s-interval '20 seconds' AND (%s::text IS NULL OR service=%s) AND (%s::text IS NULL OR (%s='ERROR' AND status>=500) OR (%s='INFO' AND status<500)) ORDER BY id DESC LIMIT 60",(incident['created_at'],args['service'],args['service'],args['severity'],args['severity'],args['severity']))
    if name=='query_metrics':
        result={'source':'Measured','prometheus':await adapters.metrics(),'http_window_seconds':20,'http':await adapters.summary(20)}
        run=await query('SELECT mode FROM investigation_runs WHERE id=%s',(run_id,),one=True)
        if run and run['mode'] in ('HYBRID_V2','HYBRID_V3','HYBRID_V3_1','HYBRID_V3_1_1','HYBRID_V3_1_2','HYBRID_V3_1_3','HYBRID_V3_1_4','HYBRID_V4','HYBRID_V4_1'):
            from .hybrid_tools import metric_windows
            result['metric_windows']=await metric_windows(incident_id)
        return result
    if name=='get_trace': return await adapters.traces(args['trace_id'])
    if name=='get_service_health': return await health(args['service'])
    if name=='search_repository':
        matches=[]
        for path in sorted(SOURCE_FILES):
            for line,text in enumerate((ROOT/path).read_text().splitlines(),1):
                if args['text'].lower() in text.lower(): matches.append({'path':path,'line':line,'text':text})
        return {'matches':matches[:40],'search_scope':sorted(SOURCE_FILES)}
    if name=='read_source_file': return read_source(**args)
    if name=='inspect_database':
        before=await adapters.database();await asyncio.sleep(1);after=await adapters.database()
        after['call_deltas']=statement_deltas(before['statements'],after['statements'])
        after['sample_seconds']=1;after['source']='Measured';return after
    if name=='inspect_redis': return await adapters.cache()
    if name=='inspect_kafka': return await adapters.kafka()
    if name=='record_hypothesis':
        if args['evidence_ids']: check_citations(args['evidence_ids'],await evidence_for(incident_id,run_id))
        hid=str(run_id)+':'+args['hypothesis_id']
        existing=await query('SELECT id FROM hypotheses WHERE id=%s',(hid,),one=True)
        if args['status']=='CREATED' and existing: raise ValueError('hypothesis already exists')
        if args['status']!='CREATED' and not existing: raise ValueError('hypothesis must first be created')
        await query('INSERT INTO hypotheses(id,incident_id,run_id,status,payload) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET status=excluded.status,payload=excluded.payload,updated_at=now()',(hid,incident_id,run_id,args['status'],Jsonb(serial(args))))
        await event(incident_id,'Hypothesis '+args['status'].title(),args,run_id=run_id)
        return {'hypothesis_id':args['hypothesis_id'],'status':args['status']}
    if name=='generate_diff':
        from .ai_patching import apply_diff
        from .patching import BASE,validate
        source=apply_diff(BASE.read_text(),args['diff'])
        return {'syntax_valid':True,'path':'services/pricing.py','sha256':validate(source),'applied':False}
    if name in ('run_tests','validate_patch'):
        from . import checkpoints
        checkpoint=await checkpoints.load(run_id)
        if checkpoint: await checkpoints.save(incident_id,run_id,'TESTING',checkpoint['payload'])
        from .ai_patching import validate_ai_diff
        result=await validate_ai_diff(args['diff'],incident_id)
        pid=str(uuid.uuid4());result['patch_id']=pid
        await query('INSERT INTO ai_patches(id,incident_id,run_id,origin,status,artifact) VALUES(%s,%s,%s,%s,%s,%s)',(pid,incident_id,run_id,'AI_GENERATED',result['status'],Jsonb(serial(result))))
        await event(incident_id,result['status'],{'patch_id':pid,'origin':'AI_GENERATED','sha256':result['sha256'],'replay':result.get('replay'),'tests':result['candidate_test']},agent='TestAgent',run_id=run_id)
        return result
    raise ValueError('tool not allowlisted')

async def execute_tool(name,arguments,incident_id,run_id,agent='Investigator',external_id=None,allowed_names=None):
    if name=='validate_generic_patch' and agent=='TestAgent' and external_id:
        from .checkpoints import previous_tool
        saved=await previous_tool(run_id,external_id)
        if saved: return saved
    call_id=str(uuid.uuid4())
    await query('INSERT INTO tool_calls(id,external_id,incident_id,run_id,agent,tool_name,arguments,status) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(call_id,external_id,incident_id,run_id,agent,name,Jsonb(serial(arguments)),'started'))
    await event(incident_id,'Tool Started',{'tool_call_id':call_id,'tool':name,'arguments':arguments},agent,run_id)
    try:
        if allowed_names is not None and name not in allowed_names: raise ValueError('tool not offered in this phase; use a currently offered tool')
        if name not in DEFINITIONS: raise ValueError('HALLUCINATED_TOOL: unknown tool name')
        if name=='submit_verification' and agent!='Critic': raise ValueError('verification requires Critic role')
        if name=='validate_generic_patch' and agent!='TestAgent': raise ValueError('generic patch validation requires TestAgent role')
        if agent=='Critic' and name!='submit_verification': raise ValueError('Critic may only submit a verification')
        if agent=='Investigator' and name in ('validate_patch','run_tests','generate_diff'): raise ValueError('patch tools require FixAgent/TestAgent phase')
        args=DEFINITIONS[name][0].model_validate(arguments).model_dump()
        if name=='validate_generic_patch': args['_execution_key']=external_id
        result=serial(await asyncio.wait_for(invoke(name,args,incident_id,run_id),timeout=100 if name in ('run_tests','validate_patch','validate_generic_patch') else 25))
        ids=[]
        if name not in ('record_hypothesis','generate_diff','complete_investigation','read_evidence','submit_verification'):
            eid='E-'+uuid.uuid4().hex[:16];ids=[eid]
            await query('INSERT INTO evidence_items(id,incident_id,run_id,tool_call_id,kind,payload) VALUES(%s,%s,%s,%s,%s,%s)',(eid,incident_id,run_id,call_id,name,Jsonb(result)))
            await event(incident_id,'Evidence Added',{'evidence_id':eid,'tool':name,'source':'Measured' if name not in ('search_repository','read_source_file') else 'Repository'},agent,run_id)
        summary=json.dumps(result,ensure_ascii=False)[:700]
        await query("UPDATE tool_calls SET finished_at=now(),status='succeeded',result_summary=%s,evidence_ids=%s WHERE id=%s",(summary,Jsonb(ids),call_id))
        await event(incident_id,'Tool Finished',{'tool_call_id':call_id,'tool':name,'status':'succeeded','evidence_ids':ids},agent,run_id)
        text=json.dumps(result,ensure_ascii=False)
        return {'tool_call_id':call_id,'evidence_ids':ids,'result':result if name=='validate_generic_patch' or len(text)<6500 else {'preview':text[:6500],'truncated':True,'complete_evidence_available_by_id':ids}}
    except Exception as exc:
        error=serial({'code':'TOOL_FAILED','type':type(exc).__name__,'message':str(exc)[:1200]})
        await query("UPDATE tool_calls SET finished_at=now(),status='failed',error=%s,evidence_ids='[]'::jsonb WHERE id=%s",(Jsonb(error),call_id))
        await event(incident_id,'Tool Failed',{'tool_call_id':call_id,'tool':name,'error':error},agent,run_id)
        return {'tool_call_id':call_id,'error':error,'evidence_ids':[]}
