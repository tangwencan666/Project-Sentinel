"""Post-evaluation operational smoke; no model invocation and no accuracy score."""
import time
from datetime import datetime,timezone
from evaluate_phase2 import api
from revalidate_pool_phase3 import snapshot,save

api('/evaluation-session/true','POST')
try:
    api('/recover','POST');time.sleep(22)
    before=api('/measured')
    api('/faults/pool_exhaustion','POST',{'duration_seconds':90});time.sleep(24)
    active=snapshot()
    print({'saturation_proven':active['saturation_proven']},flush=True)
    api('/recover','POST');time.sleep(22)
    after=api('/measured')
    healthy=all(float(s['error_pct'])==0 for s in after['http'])
    passed=active['saturation_proven'] and healthy
    save('fault-worker-live-smoke.json',{'at':datetime.now(timezone.utc).isoformat(),'scope':'Post-evaluation fault worker smoke, no Agent model invocation or accuracy score.',
        'before':before,'active':active,'after':after,'passed':passed})
    print({'passed':passed,'after_http_healthy':healthy},flush=True)
    if not passed:raise RuntimeError('post-evaluation fault worker smoke failed')
finally:
    api('/recover','POST');api('/evaluation-session/false','POST')
