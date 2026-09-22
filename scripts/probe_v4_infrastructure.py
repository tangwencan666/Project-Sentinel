"""Actual read-only adapter probe. No provider calls or diagnosis scoring."""
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
SCRIPT='''import asyncio,json
from sentinel.infra_observations import redis_observation,kafka_observation,postgres_observation
async def main():
    result={}
    for name,fn in [('redis',redis_observation),('kafka',kafka_observation),('postgres',postgres_observation)]:
        result[name]=await fn()
    print(json.dumps(result,default=str))
asyncio.run(main())
'''
run=subprocess.run(['docker','compose','run','--rm','--no-deps','-T','sentinel','python','-'],input=SCRIPT,capture_output=True,text=True,cwd=ROOT,timeout=45)
payload=json.loads(run.stdout) if run.returncode==0 else None
checks={} if payload is None else {
    'redis_measured_window':payload['redis']['window']['seconds']>=1,
    'redis_actual_memory':payload['redis']['memory_bytes']>0,
    'kafka_observed_partition':bool(payload['kafka']),
    'kafka_measured_window':all(p['window']['seconds']>=1 for p in payload['kafka']),
    'postgres_measured_window':payload['postgres']['sample_seconds']>=1,
    'postgres_actual_sessions':bool(payload['postgres']['activity']),
    'postgres_lock_query_executed':'locks' in payload['postgres']}
result={'at':datetime.now(timezone.utc).isoformat(),'passed':run.returncode==0 and all(checks.values()),
    'checks':checks,'observations':payload,'stderr':run.stderr,
    'scope':'Actual PostgreSQL read-only SQL, Redis INFO/TTL/PING, Kafka offsets; not inference accuracy.'}
with (ROOT/'evaluation/phase4/v4-infrastructure-probe.json').open('x',encoding='utf-8') as out: json.dump(result,out,indent=2)
print(json.dumps({'passed':result['passed'],'checks':checks}))
raise SystemExit(0 if result['passed'] else 1)
