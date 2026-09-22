"""Resume the interrupted operator runner without repeating its V2 investigation."""
import json
import time
from datetime import datetime,timezone
from evaluate_phase2 import api,wait_incident
from evaluate_phase3 import source_manifest
from revalidate_pool_phase3 import ROOT,save,snapshot


def main():
    originals={v:json.loads((ROOT/'evaluation/results'/f).read_text(encoding='utf-8')) for v,f in [('v2','v2-hybrid.json'),('v3','v3-context-optimized.json')]}
    hashes=source_manifest();assert all(s['source_sha256']==hashes for s in originals.values())
    persisted=json.loads((ROOT/'evaluation/pool-v2-persisted-run.json').read_text(encoding='utf-8'))
    result=json.loads((ROOT/'evaluation/pool-v2-grading-recovery.json').read_text(encoding='utf-8'))
    assert result['incident_id']=='bd325156-99e8-457d-8d41-b37145f3b984'
    result.update(recorded_incident=persisted['incident'],ledger=persisted['ledger'],context=persisted['context'])
    during=result['measured_recovery']['before']
    active=[s for s in during['database']['activity'] if s.get('application_name')=='inventory-service' and s.get('state')=='active' and 'pg_sleep' in s.get('query','')]
    error=next(h for h in during['http'] if h['service']=='inventory-service')['error_pct']
    assert len(active)>=3 and float(error)>0
    # Never replace a lost historical window with a new measurement.
    result['measured']={'before':{},'fault_active':during,'after':result['measured_recovery']['after'],
        'actor':'operator_experiment_runner','not_an_ai_repair':True,
        'provenance_note':'The runner exited on the initial grading HTTP 409 before saving its outer snapshots. Healthy-before is Unknown. Fault-active and after are exact persisted RecoveryObserver windows from this same run.'}
    save('results/v2-pool-revalidation.json',{'reason':'Same-image restart restored the dead fault worker. This is the existing single V2 trial; only grading was retried after HTTP 409.',
        'source_sha256':hashes,'source_unchanged':source_manifest()==hashes,
        'precondition':{'saturation_proven':True,'source':'Reconstructed from this run\'s persisted live RecoveryObserver database/HTTP evidence; not the lost operator precreation snapshot.',
            'active_sleep_sessions':len(active),'inventory_error_pct':error,'measured':during,
            'pool_available':None,'missing':'Original direct pool-stats snapshot was not persisted by interrupted runner; no invented value.',
            'independent_fixture_proof':'evaluation/pool-fixture-proof.json'},
        'result':result,'original_trial':next(r['incident_id'] for r in originals['v2']['results'] if r['scenario']=='pool_exhaustion')})
    api('/evaluation-session/true','POST')
    try:
        api('/recover','POST');time.sleep(24);healthy=api('/measured')
        api('/faults/pool_exhaustion','POST',{'duration_seconds':600});time.sleep(24)
        proof=snapshot();assert proof['saturation_proven'],'no model invocation without a real fault'
        checkpoint={'at':datetime.now(timezone.utc).isoformat(),'source_sha256':hashes,'healthy_before':healthy,'precondition':proof,'mode':'HYBRID_V3'}
        save('pool-v3-precreation.json',checkpoint)
        iid=api('/incidents','POST',{'mode':'HYBRID_V3','controlled_recovery':True})['id']
        save('pool-v3-run-identity.json',{'incident_id':iid,'precondition':'evaluation/pool-v3-precreation.json'})
        print(json.dumps({'version':'v3','valid_pool_incident':iid}),flush=True)
        final=wait_incident(iid,True)
        save('pool-v3-terminal.json',final)
        result=api('/incidents/'+iid+'/evaluate','POST',{'scenario_id':'pool_exhaustion'})
        result.update(recorded_incident=final,ledger=api('/incidents/'+iid+'/agent'),context=api('/incidents/'+iid+'/context'))
        api('/recover','POST');time.sleep(22)
        result['measured']={'before':healthy,'fault_active':proof['measured'],'after':api('/measured'),'actor':'operator_experiment_runner','not_an_ai_repair':True}
        save('results/v3-pool-revalidation.json',{'reason':'One first valid pool trial after independently proven inactive original injection.',
            'source_sha256':hashes,'source_unchanged':source_manifest()==hashes,'precondition':proof,'result':result,
            'original_trial':next(r['incident_id'] for r in originals['v3']['results'] if r['scenario']=='pool_exhaustion')})
        print(json.dumps({'version':'v3','correct':result['judgment']['root_cause_correct'],'service_correct':result['service_correct'],'workflow_completed':result['workflow_completed']}),flush=True)
    finally:
        api('/recover','POST');api('/evaluation-session/false','POST')


if __name__=='__main__':main()
