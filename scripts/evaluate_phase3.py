"""Single-pass real experiment. No best-of selection and no overwrite of previous suites."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import random
import time
from evaluate_phase2 import api,wait_incident

ROOT=Path(__file__).resolve().parents[1]


def source_manifest():
    paths=[p for folder in ('sentinel','services','tests') for p in (ROOT/folder).glob('*.py')]
    paths += [ROOT/'Dockerfile',ROOT/'requirements.txt',ROOT/'requirements.lock',ROOT/'compose.yaml']
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--version',choices=['v2','v3'],required=True)
    args=parser.parse_args();mode='HYBRID_V2' if args.version=='v2' else 'HYBRID_V3'
    output=ROOT/'evaluation/results'/('v2-hybrid.json' if args.version=='v2' else 'v3-context-optimized.json')
    if output.exists(): raise FileExistsError('A suite already exists; never overwrite or silently rerun wrong answers')
    frozen=json.loads((ROOT/'evaluation/baselines/manifest.json').read_text())
    hashes=source_manifest()
    for path in ('sentinel/scenarios.py','sentinel/evaluator.py','services/app.py','services/pricing.py'):
        assert hashes[path]==frozen['archived_source_hashes'][path], 'Fault/business/grading definition changed: '+path
    provider=api('/provider/check','POST')
    if provider['status']!='available': raise RuntimeError('real provider unavailable')
    scenarios=[s['scenario_id'] for s in api('/scenarios')]
    assert len(scenarios)==8
    seed=20260921
    e2e=['cache_miss','consumer_lag','retry_storm',random.Random(seed).choice(['slow_query','pool_exhaustion','n_plus_one']),'code_exception']
    suite={'version':mode,'model':provider['model'],'started_at':datetime.now(timezone.utc).isoformat(),
           'source_sha256':hashes,'scoring_unchanged':True,'scenario_order':scenarios,
           'e2e_selection':{'seed':seed,'scenarios':e2e,'selection':'DB uniformly sampled before run; all eight still run live'},
           'results':[],'completed':False,'rerun_wrong_answers':False}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as f: json.dump(suite,f,ensure_ascii=False,indent=2)
    def save():
        tmp=output.with_suffix('.pending')
        tmp.write_text(json.dumps(suite,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(output)
    api('/evaluation-session/true','POST')
    try:
        api('/traffic/true','POST')
        for scenario in scenarios:
            api('/recover','POST');time.sleep(22);before=api('/measured')
            business={r['service']:r for r in before['http']}
            if any(s not in business or float(business[s]['error_pct'])>0 for s in ('gateway','order-service','payment-service')):
                raise RuntimeError('Healthy pre-fault workload prerequisite failed; no fault trial started')
            api('/faults/'+scenario,'POST',{'duration_seconds':600});time.sleep(24);during=api('/measured')
            iid=api('/incidents','POST',{'mode':mode,'controlled_recovery':True})['id']
            print(json.dumps({'scenario':scenario,'mode':mode,'incident_id':iid}),flush=True)
            row={'scenario':scenario,'mode':mode,'incident_id':iid}
            try:
                final=wait_incident(iid,True)
                row.update(api('/incidents/'+iid+'/evaluate','POST',{'scenario_id':scenario}))
                row['recorded_incident']=final
                row['ledger']=api('/incidents/'+iid+'/agent')
                row['context']=api('/incidents/'+iid+'/context')
                print(json.dumps({'scenario':scenario,'correct':row['judgment']['root_cause_correct'],
                    'service_correct':row['service_correct'],'critic':(row.get('critic') or {}).get('verdict'),
                    'tools':row['tool_calls'],'tokens':row['ledger']['usage']['total_tokens']}),flush=True)
            except Exception as exc:
                row.update(runner_error=type(exc).__name__+': '+str(exc),judgment={'root_cause_correct':False},service_correct=False)
                print(json.dumps({'scenario':scenario,'failure':row['runner_error']}),flush=True)
            suite['results'].append(row);save()
            api('/recover','POST');time.sleep(22)
            row['measured']={'before':before,'fault_active':during,'after':api('/measured'),
                             'actor':'operator_experiment_runner','not_an_ai_repair':True};save()
        assert source_manifest()==hashes,'source changed during frozen experiment'
        suite['completed']=True;suite['finished_at']=datetime.now(timezone.utc).isoformat();save()
    finally:
        api('/recover','POST');api('/evaluation-session/false','POST');save()
    output.chmod(0o444)


if __name__=='__main__': main()
