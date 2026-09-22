"""Operator-supplied patch integration test. This DOES NOT test or simulate an LLM.
Runs an actual regression, deployment, live-fault verification and rollback.
"""
import json
import time
from pathlib import Path
from verify_lab import api, checkout

result={'actor':'operator_integration_test','llm_verified':False}
try:
    api('/recover','POST');api('/rollback','POST');api('/traffic/true','POST')
    api('/faults/code_exception','POST',{'duration_seconds':180})
    assert checkout()[0]==502
    incident=api('/incidents','POST')['id']
    source=Path('services/pricing.py').read_text(encoding='utf-8')
    candidate=source.replace('(1 - discount)','(1 - (discount if discount is not None else 0))')
    patch=api('/incidents/'+incident+'/patch','POST',{'source':candidate})
    assert patch['validated'],patch
    result.update(incident_id=incident,sha256=patch['sha256'],baseline_tests=patch['baseline_test'],candidate_tests=patch['candidate_test'],diff=patch['diff'])
    api('/incidents/'+incident+'/deploy','POST',{'sha256':patch['sha256']})
    for _ in range(15):
        time.sleep(3)
        data=api('/incidents/'+incident)
        if data.get('verification'): break
    assert data['verification']['verified'],data['verification']
    result['verification']=data['verification']
    api('/rollback','POST')
    assert checkout()[0]==502,'Rollback did not restore original reproducer failure'
    result['rollback_reproduces']=True
    result['passed']=True
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
finally:
    api('/recover','POST');api('/rollback','POST');api('/traffic/true','POST')
    Path('docs/repair-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
