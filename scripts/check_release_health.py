"""Read-only post-evaluation health snapshot; no model, fault, or process mutations."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'evaluation/phase4/release-health-first.json'
SERVICES = {'gateway', 'user-service', 'order-service', 'payment-service', 'inventory-service',
            'notification-service', 'postgres', 'redis', 'redpanda', 'jaeger', 'otel-collector',
            'prometheus', 'sentinel', 'loadgen'}

PROGRAM = '''
import asyncio,json,httpx
from sentinel.api import redis
async def main():
    result={}
    async with httpx.AsyncClient(timeout=10) as client:
        for service in ('gateway','user-service','order-service','payment-service','inventory-service','notification-service'):
            response=await client.get('http://'+service+':8000/health')
            result[service]={'http_status':response.status_code,'body':response.json()}
    print(json.dumps({'services':result,'evaluation_lock_exists':bool(await redis.exists('control:evaluation_lock'))}))
asyncio.run(main())
'''


def main():
    if OUTPUT.exists():
        raise FileExistsError('Retain the first release health snapshot')
    suite = json.loads((ROOT / 'evaluation/results/v4.1-first-controlled.json').read_text(encoding='utf-8'))
    assert suite['completed'] and len(suite['results']) == 8

    def command(args, **kwargs):
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                              check=True, timeout=60, **kwargs).stdout

    def api(path):
        with urllib.request.urlopen('http://127.0.0.1:18082/api' + path, timeout=30) as response:
            return json.load(response)

    raw = command(['docker', 'compose', 'ps', '--format', 'json'])
    containers = [json.loads(line) for line in raw.splitlines() if line.strip()]
    containers = [{key: row.get(key) for key in ('Service', 'State', 'Health', 'Image')}
                  for row in containers if row.get('Service') in SERVICES]
    health = json.loads(command(['docker', 'compose', 'exec', '-T', 'sentinel', 'python', '-'], input=PROGRAM))
    before = api('/evidence/queue')
    time.sleep(3)
    after = api('/evidence/queue')
    old = {row['partition']: row for row in before}
    queue_progress = bool(after) and all(row['lag'] <= 5 and row['partition'] in old
        and row['committed_offset'] > old[row['partition']]['committed_offset'] for row in after)
    overview = api('/overview')
    measured = api('/measured')
    checks = {
        'fourteen_services_running': len(containers) == 14 and {r['Service'] for r in containers} == SERVICES
            and all(r['State'] == 'running' and r['Health'] in ('healthy', '', None) for r in containers),
        'six_http_health_checks': all(r['http_status'] == 200 for r in health['services'].values()),
        'consumer_progress_and_low_lag': queue_progress,
        'evaluation_lock_released': not health['evaluation_lock_exists'],
        'no_active_faults': not overview['active_faults'],
        'traffic_enabled': overview['traffic_enabled'],
        'healthy_http_window': bool(measured['http']) and all(float(r['error_pct']) == 0 for r in measured['http']),
    }
    result = {'at': datetime.now(timezone.utc).isoformat(), 'passed': all(checks.values()),
        'checks': checks, 'containers': containers, 'health': health, 'queue_before': before,
        'queue_after': after, 'measured': measured, 'active_faults': overview['active_faults'],
        'scope': 'Read-only bounded observation; running-only infrastructure containers have no Docker healthcheck.'}
    with OUTPUT.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    OUTPUT.chmod(0o444)
    print(json.dumps({'passed': result['passed'], 'checks': checks}))
    if not result['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
