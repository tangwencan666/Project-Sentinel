"""Read-only telemetry capacity observations during the new qualification."""
import json
from datetime import datetime,timezone
from pathlib import Path
import subprocess
import time
import urllib.request

root=Path(__file__).resolve().parents[1]
path=root/'evaluation/phase4/jaeger-bounded-profile.json'
result={'scope':'Read-only observations during qualification; not a diagnosis score.',
        'retention_traces':10000,'container_limit_mib':768,'go_soft_limit_mib':640,'samples':[]}
with path.open('x',encoding='utf-8') as out: json.dump(result,out)
for index in range(45):
    observation={'at':datetime.now(timezone.utc).isoformat()}
    stats=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}','project-sentinel-jaeger-1'],capture_output=True,text=True,timeout=15)
    observation['stats']=json.loads(stats.stdout) if stats.returncode==0 else {'error':stats.stderr}
    start=time.monotonic()
    try:
        with urllib.request.urlopen('http://127.0.0.1:18082/api/evidence/traces',timeout=15) as response: traces=json.load(response)
        observation.update(query_seconds=time.monotonic()-start,trace_count=len(traces),query_succeeded=True)
    except Exception as exc: observation.update(query_seconds=time.monotonic()-start,query_succeeded=False,error=str(exc))
    result['samples'].append(observation)
    suite=json.loads((root/'evaluation/phase4/v3.1.2-qualification.continued-1.json').read_text(encoding='utf-8'))
    done=suite.get('completed') or 'runner_error' in suite
    result['observation_finished']=bool(done)
    path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    if done: break
    time.sleep(20)
print(json.dumps({'samples':len(result['samples']),'query_failures':sum(not s['query_succeeded'] for s in result['samples'])}))
