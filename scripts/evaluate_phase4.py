"""First controlled runs, predeclared order, immutable suite and no answer-based reruns."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
import zipfile
import stat
from evaluate_phase2 import api,wait_incident
from evaluate_phase3 import source_manifest
from runtime_source_gate import verify

ROOT=Path(__file__).resolve().parents[1]
ORDER=['pool_exhaustion','n_plus_one','cache_miss','consumer_lag','downstream_timeout','code_exception','slow_query','retry_storm']

def validity(scenario,samples):
    """Operator-only fixture check. Results never enter Investigator input."""
    latest=samples[-1];http={r['service']:r for r in latest['measured']['http']}
    active=[r for r in latest['database']['activity'] if r.get('application_name')=='inventory-service' and r.get('state')=='active' and 'pg_sleep' in r.get('query','')]
    statements=latest['database']['statements']
    previous=samples[0]['database']['statements']
    old={r['queryid']:r['calls'] for r in previous}
    moving=[r for r in statements if r['queryid'] in old and r['calls']>old[r['queryid']]]
    traces=latest['traces'];logs=latest['logs']
    if scenario=='pool_exhaustion': return len(active)>=4 and float(http.get('inventory-service',{}).get('error_pct',0))>0
    if scenario=='slow_query':
        # Active-session sampling can fall between requests. Require an observed
        # PgSleep in either sample AND a moving sleep-query counter AND latency.
        observed_sleep=any(r.get('application_name')=='inventory-service' and r.get('state')=='active'
                           and r.get('wait_event')=='PgSleep' for sample in samples for r in sample['database']['activity'])
        moving_sleep=any('pg_sleep' in r['query'] for r in moving)
        return observed_sleep and moving_sleep and http.get('inventory-service',{}).get('p95_ms',0)>1000
    if scenario=='n_plus_one': return any('products WHERE id' in r['query'] and r['calls']-old[r['queryid']]>=40 for r in moving)
    if scenario=='cache_miss': return latest['cache'].get('catalog_ttl')==-2 and any('FROM products' in r['query'] for r in moving)
    if scenario=='consumer_lag':
        before={r['partition']:r for r in samples[0]['queue']}
        return any(r['partition'] in before and r['end_offset']>before[r['partition']]['end_offset'] and r['committed_offset']==before[r['partition']]['committed_offset'] and r['lag']>5 for r in latest['queue'])
    if scenario=='downstream_timeout':
        spans=[(t['processes'].get(s['processID'],{}).get('serviceName'),s) for t in traces for s in t['spans']]
        payment_slow=any(service=='payment-service' and span['duration_us']>=2800000 for service,span in spans)
        caller_timeout=any(service=='order-service' and 'ReadTimeout' in json.dumps(span.get('tags',[]))
                           and 1800000<=span['duration_us']<=2800000 for service,span in spans)
        return payment_slow and caller_timeout and float(http.get('order-service',{}).get('error_pct',0))>0
    if scenario=='code_exception': return any(r.get('service')=='order-service' and 'TypeError' in str(r.get('error')) for r in logs)
    if scenario=='retry_storm': return float(http.get('payment-service',{}).get('throughput_rps',0))/max(float(http.get('order-service',{}).get('throughput_rps',0)),.001)>2 and float(http.get('payment-service',{}).get('error_pct',0))>0
    return False

def snapshot():
    return {'at':datetime.now(timezone.utc).isoformat(),'measured':api('/measured'),
            'database':api('/evidence/database'),'cache':api('/evidence/cache'),
            'queue':api('/evidence/queue'),'logs':api('/evidence/logs'),'traces':api('/evidence/traces')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--version',choices=['v3.1','v4','v4.1'],required=True)
    parser.add_argument('--continue-preflight',action='store_true',help='Append only unstarted scenarios after an operator fixture-check interruption; never rerun an existing trial.')
    args=parser.parse_args();mode={'v3.1':'HYBRID_V3_1','v4':'HYBRID_V4','v4.1':'HYBRID_V4_1'}[args.version]
    output=ROOT/'evaluation/results'/f'{args.version}-first-controlled.json'
    if output.exists() and not args.continue_preflight: raise FileExistsError('Formal suite already reserved; never overwrite or rerun wrong answers.')
    hashes=source_manifest()
    test_name='reliability-tests-final.json' if args.version=='v4.1' else 'reliability-tests-v4.json' if args.version=='v4' else 'reliability-tests.json'
    tests=json.loads((ROOT/'evaluation/phase4'/test_name).read_text(encoding='utf-8'))
    assert tests['exit_code']==0 and tests['source_sha256']==hashes,'Run reliability gate against exact current code first'
    if args.version in ('v4','v4.1'):
        qualified=json.loads((ROOT/'evaluation/phase4/v3.1.4-qualification.json').read_text(encoding='utf-8'))
        assert qualified['completed'] and qualified['passed'] and len(qualified['results'])==5
        assert all(r['passed'] for r in qualified['results'])
    if args.version=='v4.1':
        for proof_name in ('crash-resume-followup.json','static-audit-final.json','adversarial-audit-final.json','ui-e2e-final.json'):
            assert json.loads((ROOT/'evaluation/phase4'/proof_name).read_text(encoding='utf-8'))['passed'],proof_name
    container_proof=verify(hashes,running=True)
    benchmark='sentinel-benchmark-v2' if args.version=='v4.1' else 'sentinel-benchmark-v1'
    manifest=json.loads((ROOT/'evaluation/benchmarks'/benchmark/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['protected_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    assert set(ORDER)=={s['scenario_id'] for s in api('/scenarios')}
    provider=api('/provider')
    assert provider['configured'] and provider['model']=='deepseek-chat'
    archive=ROOT/'evaluation/phase4'/f'{args.version}-framework.zip'
    if not args.continue_preflight:
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
            for name in hashes: z.write(ROOT/name,name)
            if args.version=='v4.1':
                for folder in ('scripts','web','docs'):
                    for file in sorted((ROOT/folder).rglob('*')):
                        if file.is_file() and file.suffix in ('.py','.cjs','.js','.html','.css','.md'): z.write(file,file.relative_to(ROOT).as_posix())
        archive.chmod(0o444)
    suite={'version':mode,'model':provider['model'],'benchmark_id':manifest['benchmark_id'],
        'ground_truth_version':manifest['ground_truth_version'],'started_at':datetime.now(timezone.utc).isoformat(),
        'source_sha256':hashes,'container_source_verification':container_proof,'scenario_order':ORDER,'results':[],'completed':False,'rerun_wrong_answers':False,
        'comparison_limitations':manifest.get('comparison_limitations','V4 inherits qualified 3.1.4 runtime repairs and bounded Jaeger retention. It is not an isolated compression ablation. Infrastructure restart may change cache/cumulative-counter warmup.'),
        'budget_policy':{'exploration_tools':28,'evidence_completion':8,'correction':12,'submission_retry':3,
            'schema_repair':12,'provider_retry':10,'round_ceiling':20,'legacy_round_ceiling':12,
            'per_structured_output_repairs':2,'provider_output_tokens':2500,'provider_total_tokens':300000,
            'note':'Additional completion/correction budgets explicitly differ from V3; this is a runtime intervention, not an isolated context-compression comparison.'}}
    prefix=[]
    if args.continue_preflight:
        suite=json.loads(output.read_text(encoding='utf-8'))
        assert not suite['completed'] and suite['source_sha256']==hashes
        assert suite.get('runner_error','').startswith('Fixture invalid before model dispatch:'),'Continuation is restricted to pre-model fixture checks'
        assert all(r.get('ledger') and r.get('run_status') in ('failed','completed') for r in suite['results'])
        assert [r['scenario'] for r in suite['results']]==ORDER[:len(suite['results'])]
        prefix=json.loads(json.dumps(suite['results']))
        predecessor=output.with_name(output.stem+'.interrupted-'+str(len(suite.get('continuations',[]))+1)+'.json')
        with predecessor.open('xb') as stream: stream.write(output.read_bytes())
        predecessor.chmod(stat.S_IREAD)
        suite.setdefault('continuations',[]).append({'at':datetime.now(timezone.utc).isoformat(),
            'predecessor':str(predecessor.relative_to(ROOT)),'sha256':hashlib.sha256(predecessor.read_bytes()).hexdigest(),
            'reason':suite.pop('runner_error'),'preserved_trial_count':len(prefix),
            'policy':'Prior trial records are unchanged; append only scenarios with no previous model dispatch.'})
        output.chmod(stat.S_IREAD|stat.S_IWRITE)
    else:
        with output.open('x',encoding='utf-8') as stream: json.dump(suite,stream,indent=2)
    def save():
        assert suite['results'][:len(prefix)]==prefix,'Previously recorded trials must never change'
        pending=output.with_suffix('.pending');pending.write_text(json.dumps(suite,ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(output)
    api('/evaluation-session/true','POST')
    try:
        api('/traffic/true','POST')
        for scenario in ORDER:
            if any(r['scenario']==scenario for r in suite['results']): continue
            api('/recover','POST');time.sleep(24)
            for health_attempt in range(5):
                before=api('/measured')
                queue_before=api('/evidence/queue');time.sleep(3);queue_after=api('/evidence/queue')
                old={r['partition']:r for r in queue_before}
                consumer_ready=bool(queue_after) and all(r['lag']<=5 and r['committed_offset'] is not None
                    and r['partition'] in old and old[r['partition']]['committed_offset'] is not None
                    and r['committed_offset']>old[r['partition']]['committed_offset'] for r in queue_after)
                suite.setdefault('healthy_prerequisites',[]).append({'scenario':scenario,'attempt':health_attempt+1,
                    'measured':before,'queue_before':queue_before,'queue_after':queue_after,'consumer_ready':consumer_ready});save()
                if before['http'] and all(float(r['error_pct'])==0 for r in before['http']) and consumer_ready: break
                if health_attempt==4: raise RuntimeError('Fixture invalid before model dispatch: healthy prerequisite for '+scenario)
                time.sleep(24)
            api('/faults/'+scenario,'POST',{'duration_seconds':600});time.sleep(24)
            samples=[snapshot()];time.sleep(3);samples.append(snapshot())
            valid=validity(scenario,samples)
            fixture={'scenario':scenario,'valid':valid,'samples':samples}
            proof=ROOT/'evaluation/phase4'/f'{args.version}-{scenario}-fixture.json'
            if proof.exists():
                original_proof=proof;attempt=2
                while proof.exists():
                    proof=original_proof.with_name(original_proof.stem+f'.attempt-{attempt}.json');attempt+=1
            with proof.open('x',encoding='utf-8') as stream: json.dump(fixture,stream,ensure_ascii=False,indent=2)
            if not valid: raise RuntimeError('Fixture invalid before model dispatch: '+scenario)
            iid=api('/incidents','POST',{'mode':mode,'controlled_recovery':True})['id']
            row={'scenario':scenario,'mode':mode,'incident_id':iid,'fixture_valid':True,'fixture_proof':str(proof.relative_to(ROOT))};suite['results'].append(row);save()
            print(json.dumps({'scenario':scenario,'mode':mode,'incident_id':iid}),flush=True)
            try:
                final=wait_incident(iid,True);row['recorded_incident']=final;save()
                try: row.update(api('/incidents/'+iid+'/evaluate','POST',{'scenario_id':scenario}))
                except Exception as exc: row['grading_error']=str(exc);row['grading_status']='ungraded'
                row['ledger']=api('/incidents/'+iid+'/agent');row['context']=api('/incidents/'+iid+'/context')
                if args.version=='v4.1':
                    row['runtime_diagnostics']=api('/incidents/'+iid+'/runtime')
                    current_run=next(r for r in row['ledger']['runs'] if r['id']==row['ledger']['run_id'])
                    row['workflow_completed']=current_run['status']=='completed';row['run_status']=current_run['status']
                    row.setdefault('run_id',current_run['id']);row.setdefault('error',current_run.get('error'))
                    if not row.get('duration_seconds') and current_run.get('finished_at'):
                        row['duration_seconds']=(datetime.fromisoformat(current_run['finished_at'])-datetime.fromisoformat(current_run['started_at'])).total_seconds()
                print(json.dumps({'scenario':scenario,'workflow':row.get('workflow_completed'),'correct':row.get('judgment',{}).get('root_cause_correct'),'error':row.get('error'),'grading_error':row.get('grading_error')}),flush=True)
            except Exception as exc:
                row['runner_error']=str(exc);save();raise
            save();api('/recover','POST');time.sleep(24)
            row['measured']={'before':before,'fault_active':samples[-1]['measured'],'after':api('/measured'),
                             'actor':'operator_experiment_runner','not_an_ai_repair':True};save()
        assert source_manifest()==hashes,'Framework changed during experiment'
        suite['completed']=True;suite['finished_at']=datetime.now(timezone.utc).isoformat();save()
    except Exception as exc:
        suite['runner_error']=str(exc);save();raise
    finally:
        api('/recover','POST');api('/evaluation-session/false','POST');save()
        output.chmod(0o444)
if __name__=='__main__': main()
