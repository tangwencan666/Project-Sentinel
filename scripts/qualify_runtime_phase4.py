"""Preregistered five-case runtime qualification, excluded from RCA benchmark scores."""
from datetime import datetime,timezone
import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile
from evaluate_phase2 import api,wait_incident
from evaluate_phase3 import source_manifest
from runtime_source_gate import verify
from evaluate_phase4 import snapshot,validity

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',choices=['v3.1.1','v3.1.2','v3.1.3','v3.1.4'],default='v3.1.1')
    parser.add_argument('--continue-from',help='Preserve a pre-model interrupted qualification and append only unstarted scenarios into a new artifact.')
    args=parser.parse_args()
    for ready_attempt in range(15):
        try:
            api('/overview');break
        except Exception:
            if ready_attempt==14: raise
            time.sleep(1)
    prefix=ROOT/'evaluation/phase4'
    version=args.version
    prereg_path=prefix/('runtime-followup-preregistration.json' if version=='v3.1.1' else f'runtime-followup-{version}-preregistration.json')
    prereg=json.loads(prereg_path.read_text(encoding='utf-8'))
    original=json.loads((ROOT/'evaluation/results/v3.1-first-controlled.json').read_text(encoding='utf-8'))
    assert original['completed'] and len(original['results'])==8
    tests=json.loads((prefix/f'reliability-tests-{version}.json').read_text(encoding='utf-8'));hashes=source_manifest()
    assert tests['exit_code']==0 and tests['source_sha256']==hashes
    container_proof=verify(hashes,running=True)
    manifest=json.loads((ROOT/'evaluation/benchmarks/sentinel-benchmark-v1/manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['protected_sha256'].items(): assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    output=prefix/f'{version}-qualification.json'
    if args.continue_from:
        number=1
        while (prefix/f'{version}-qualification.continued-{number}.json').exists(): number+=1
        output=prefix/f'{version}-qualification.continued-{number}.json'
    if output.exists(): raise FileExistsError('Retain qualification attempts; never overwrite an existing run.')
    archive=prefix/f'{version}-framework.zip'
    if not args.continue_from:
        with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
            for name in hashes: z.write(ROOT/name,name)
        archive.chmod(0o444)
    result={'mode':prereg['candidate_version'],'model':'deepseek-chat','scope':'RUNTIME_QUALIFICATION_NOT_ACCURACY',
        'preregistration':str(prereg_path.relative_to(ROOT)),
        'first_controlled_result_sha256':hashlib.sha256((ROOT/'evaluation/results/v3.1-first-controlled.json').read_bytes()).hexdigest(),
        'source_sha256':hashes,'started_at':datetime.now(timezone.utc).isoformat(),'results':[],'completed':False,'passed':False}
    result['container_source_verification']=container_proof
    preserved=[]
    if args.continue_from:
        assert Path(args.continue_from).name==args.continue_from
        previous=prefix/args.continue_from
        result=json.loads(previous.read_text(encoding='utf-8'))
        assert not result['completed'] and result['source_sha256']==hashes and 'runner_error' in result
        assert all('workflow_completed' in row for row in result['results']), 'Never rerun an already dispatched incomplete trial'
        assert [row['scenario'] for row in result['results']]==prereg['preregistered_scenarios'][:len(result['results'])]
        preserved=json.loads(json.dumps(result['results']))
        result['continuation']={'previous':args.continue_from,'sha256':hashlib.sha256(previous.read_bytes()).hexdigest(),
            'previous_error':result.pop('runner_error'),'preserved_trials':len(preserved),
            'reason':'Pre-model operator prerequisite interruption; exact framework unchanged, no model trial repeated.'}
    with output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
    def save():
        assert result['results'][:len(preserved)]==preserved
        pending=output.with_suffix('.pending');pending.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');pending.replace(output)
    api('/evaluation-session/true','POST')
    try:
        api('/traffic/true','POST')
        for scenario in prereg['preregistered_scenarios']:
            if any(row['scenario']==scenario for row in result['results']): continue
            result['operator_stage']={'scenario':scenario,'stage':'preflight_before_model'};save()
            api('/recover','POST');time.sleep(24)
            for health_attempt in range(5):
                before=api('/measured')
                result.setdefault('healthy_prerequisites',[]).append({'scenario':scenario,'attempt':health_attempt+1,'measured':before});save()
                if before['http'] and all(float(r['error_pct'])==0 for r in before['http']): break
                if health_attempt==4: raise RuntimeError('Pre-model healthy prerequisite failed after five measured windows')
                time.sleep(24)
            api('/faults/'+scenario,'POST',{'duration_seconds':600});time.sleep(24)
            def bounded_snapshot():
                for attempt in range(3):
                    try: return snapshot()
                    except Exception as exc:
                        result.setdefault('operator_snapshot_errors',[]).append({'scenario':scenario,'attempt':attempt+1,'error':str(exc),'at':datetime.now(timezone.utc).isoformat()});save()
                        if attempt==2: raise
                        time.sleep(3)
            samples=[bounded_snapshot()];time.sleep(3);samples.append(bounded_snapshot())
            if not validity(scenario,samples):
                result['fixture_failure']={'scenario':scenario,'samples':samples};save();raise RuntimeError('Qualification preflight did not establish an active fault')
            iid=api('/incidents','POST',{'mode':prereg['candidate_version'],'controlled_recovery':True})['id']
            row={'scenario':scenario,'incident_id':iid,'fixture_samples':samples};result['results'].append(row);save()
            print(json.dumps({'scenario':scenario,'incident_id':iid}),flush=True)
            final=wait_incident(iid,True);ledger=api('/incidents/'+iid+'/agent');context=api('/incidents/'+iid+'/context')
            runs=[r for r in ledger['runs'] if r['id']==ledger['run_id']];run=runs[-1]
            patch=(final.get('report') or {}).get('patch') or {}
            row.update(recorded_incident=final,ledger=ledger,context=context,run_id=ledger['run_id'],
                workflow_completed=run['status']=='completed',error=run.get('error'),
                patch_verified=bool(patch.get('candidate_verified')),graded=False)
            row['passed']=row['workflow_completed'] and (scenario!='code_exception' or row['patch_verified'])
            print(json.dumps({'scenario':scenario,'workflow':row['workflow_completed'],'patch_verified':row['patch_verified'],'passed':row['passed'],'error':row['error']}),flush=True)
            save();api('/recover','POST');time.sleep(24)
            row['measured']={'before':before,'fault_active':samples[-1]['measured'],'after':api('/measured'),
                             'actor':'operator_qualification_runner','not_an_ai_repair':True};save()
        assert source_manifest()==hashes
        result['completed']=True;result['passed']=all(r['passed'] for r in result['results'])
        result['finished_at']=datetime.now(timezone.utc).isoformat();save()
    except Exception as exc:
        result['runner_error']=str(exc);result['runner_error_type']=type(exc).__name__;save();raise
    finally:
        api('/recover','POST');api('/evaluation-session/false','POST');save();output.chmod(0o444)
    print(json.dumps({'qualification_completed':True,'passed':result['passed']}),flush=True)
    if not result['passed']: raise SystemExit(1)
if __name__=='__main__': main()
