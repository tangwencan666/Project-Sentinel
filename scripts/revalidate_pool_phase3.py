"""Repair an independently evidenced invalid fixture, preserving every original trial.

This is not a retry based on model correctness. No model runs until the unchanged
pool scenario demonstrably holds connections and produces HTTP failures.
"""
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime,timezone
from evaluate_phase2 import api,wait_incident
from evaluate_phase3 import source_manifest

ROOT=Path(__file__).resolve().parents[1]


def save(name,value):
    path=ROOT/'evaluation'/name
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)


def snapshot():
    measured=api('/measured');database=api('/evidence/database')
    active=[s for s in database.get('activity',[]) if s.get('application_name')=='inventory-service' and s.get('state')=='active' and 'pg_sleep' in s.get('query','')]
    inventory=next(s for s in measured['db_pool'] if s['service']=='inventory-service')
    stats=inventory.get('pool-stats',{}).get('body',{}).get('pool',{})
    direct=None
    if stats.get('pool_available') is None:
        # The aggregate observer stops after /health fails under saturation.
        # Read the existing non-DB /pool-stats endpoint directly, preserving both observations.
        program="import json,httpx; r=httpx.get('http://inventory-service:8000/pool-stats',timeout=5); r.raise_for_status(); print(json.dumps(r.json()))"
        direct=json.loads(subprocess.check_output(['docker','compose','exec','-T','sentinel','python','-c',program],cwd=ROOT,text=True))
        stats=direct['pool']
    http=next((h for h in measured['http'] if h['service']=='inventory-service'),{})
    proven=len(active)>=3 and stats.get('pool_available')==0 and float(http.get('error_pct',0))>0
    return {'measured':measured,'database':database,'direct_pool_stats':direct,'active_sleep_sessions':len(active),'pool_available':stats.get('pool_available'),
            'inventory_error_pct':http.get('error_pct'),'saturation_proven':proven}


def main():
    originals={v:json.loads((ROOT/'evaluation/results'/file).read_text(encoding='utf-8')) for v,file in [('v2','v2-hybrid.json'),('v3','v3-context-optimized.json')]}
    assert all(s['completed'] for s in originals.values()),'wait for both original suites to end'
    hashes=source_manifest();assert all(s['source_sha256']==hashes for s in originals.values())
    for version in originals:
        assert not (ROOT/f'evaluation/results/{version}-pool-revalidation.json').exists(),'single valid supplementary trial only'
    api('/evaluation-session/true','POST')
    try:
        prior_proof=ROOT/'evaluation/pool-fixture-proof.json'
        if prior_proof.exists():
            previous=json.loads(prior_proof.read_text(encoding='utf-8'))
            assert previous['status']=='not_restored' and previous['source_unchanged']
            assert not any(s['saturation_proven'] for s in previous['before']) and all(s['active_sleep_sessions']>=3 for s in previous['after'])
            retained=ROOT/'evaluation/pool-fixture-proof-attempt1.json';assert not retained.exists()
            prior_proof.rename(retained)
            before=previous['before'];prior_image=previous['image_before'];relevant=previous['shutdown_error_lines']
            api('/recover','POST');time.sleep(22)
            api('/faults/pool_exhaustion','POST',{'duration_seconds':600});time.sleep(24)
        else:
            api('/recover','POST');time.sleep(22)
            api('/faults/pool_exhaustion','POST',{'duration_seconds':600});time.sleep(24)
            before=[snapshot() for _ in range(3)]
            if any(s['saturation_proven'] for s in before):
                save('pool-fixture-proof.json',{'status':'not_reproduced_before_restart','before':before,'replacement_allowed':False})
                raise RuntimeError('fixture currently works; no automatic replacement authorized by evidence')
            prior_image=subprocess.check_output(['docker','inspect','--format','{{.Image}}','project-sentinel-inventory-service-1'],text=True).strip()
            subprocess.run(['docker','compose','restart','inventory-service'],cwd=ROOT,check=True,timeout=40)
            time.sleep(24)
            log=subprocess.check_output(['docker','compose','logs','--no-color','inventory-service'],cwd=ROOT,text=True)
            relevant=[line for line in log.splitlines() if any(x in line for x in ('Task exception','exhaust','redis.exceptions.ConnectionError','Error -3','Error 111'))]
        after=[snapshot() for _ in range(3)]
        post_image=subprocess.check_output(['docker','inspect','--format','{{.Image}}','project-sentinel-inventory-service-1'],text=True).strip()
        proven=any(s['saturation_proven'] for s in after) and prior_image==post_image
        save('pool-fixture-proof.json',{'at':datetime.now(timezone.utc).isoformat(),'status':'restored_by_service_restart' if proven else 'not_restored',
            'before':before,'after':after,'image_before':prior_image,'image_after':post_image,'source_unchanged':source_manifest()==hashes,
            'shutdown_error_lines':relevant,'replacement_allowed':proven,'retained_inconclusive_probe':'evaluation/pool-fixture-proof-attempt1.json',
            'observer_note':'Under saturation the aggregate health observer does not reach /pool-stats; the operator directly measures that existing endpoint. No saturation criterion was relaxed.',
            'policy':'Original attempts remain immutable. One first valid trial per version; no selection by answer correctness.'})
        if not proven: raise RuntimeError('cannot prove pool saturation; do not evaluate nonexistent fault')
        print(json.dumps({'fixture_restored':True,'before_active':[s['active_sleep_sessions'] for s in before],'after_active':[s['active_sleep_sessions'] for s in after]}),flush=True)
        for version,original in originals.items():
            api('/recover','POST');time.sleep(24);healthy=api('/measured')
            api('/faults/pool_exhaustion','POST',{'duration_seconds':600});time.sleep(24)
            proof=snapshot()
            if not proof['saturation_proven']: raise RuntimeError('pool precondition failed; model was not invoked')
            iid=api('/incidents','POST',{'mode':original['version'],'controlled_recovery':True})['id']
            print(json.dumps({'version':version,'valid_pool_incident':iid}),flush=True)
            final=wait_incident(iid,True)
            result=api('/incidents/'+iid+'/evaluate','POST',{'scenario_id':'pool_exhaustion'})
            result.update(recorded_incident=final,ledger=api('/incidents/'+iid+'/agent'),context=api('/incidents/'+iid+'/context'))
            api('/recover','POST');time.sleep(22)
            result['measured']={'before':healthy,'fault_active':proof['measured'],'after':api('/measured'),'actor':'operator_experiment_runner','not_an_ai_repair':True}
            record={'reason':'Original pool injection did not hold connections; same-image restart restored the existing fault worker.',
                    'source_sha256':hashes,'precondition':proof,'result':result,'source_unchanged':source_manifest()==hashes,'original_trial':next(r['incident_id'] for r in original['results'] if r['scenario']=='pool_exhaustion')}
            save(f'results/{version}-pool-revalidation.json',record)
            print(json.dumps({'version':version,'correct':result['judgment']['root_cause_correct'],'service_correct':result['service_correct'],'workflow_completed':result['workflow_completed']}),flush=True)
    finally:
        api('/recover','POST');api('/evaluation-session/false','POST')


if __name__=='__main__':main()
