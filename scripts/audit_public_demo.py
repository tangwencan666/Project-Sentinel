"""Actual container + HTTP read-only boundary audit. No live agent request is sent."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='public-security-first.json');args=parser.parse_args()
    if Path(args.output).name!=args.output:raise ValueError('Use a report filename')
    target=ROOT/'artifacts/phase5'/args.output
    if target.exists():raise FileExistsError('Preserve original audit')
    checks=[]
    def request(path,method='GET',headers=None):
        req=urllib.request.Request('http://127.0.0.1:18082'+path,method=method,headers=headers or {},data=b'{}' if method not in ('GET','HEAD') else None)
        try:
            with urllib.request.urlopen(req,timeout=15) as r:return r.status,r.read()
        except urllib.error.HTTPError as e:return e.code,e.read()
    for method in ('POST','PUT','PATCH','DELETE'):
        for endpoint in ('/api/faults/code_exception','/api/incidents','/api/incidents/00000000-0000-0000-0000-000000000001/deploy','/api/provider/check','/api/database/query','/api/tools/shell','/api/config','/api/upload','/api/secrets'):
            status,_=request(endpoint,method);checks.append({'action':method+' '+endpoint,'status':status,'passed':status==403})
    for path in ('/api/portfolio/demo','/api/portfolio/evaluation','/api/portfolio/patch','/api/portfolio/report'):
        status,_=request(path);checks.append({'action':'GET '+path,'status':status,'passed':status==200})
    status,_=request('/live.html');checks.append({'action':'Live workspace unavailable','status':status,'passed':status==403})
    status,_=request('/',headers={'Host':'attacker.invalid'});checks.append({'action':'Host allowlist','status':status,'passed':status==400})
    command=['docker','compose','exec','-T','sentinel-demo','python','-']
    program='''import json,os,importlib.util
from pathlib import Path
blocked=False
try: Path('/app/phase5-write-probe').write_text('BOUNDARY_TEST')
except OSError: blocked=True
else: Path('/app/phase5-write-probe').unlink()
print(json.dumps({'uid':os.getuid(),'filesystem_write_denied':blocked,
 'forbidden_modules_absent':all(importlib.util.find_spec(x) is None for x in ('sentinel.provider','sentinel.api','sentinel.tool_registry','psycopg','redis','aiokafka')),
 'secret_environment_absent':not any(os.getenv(k) for k in ('LLM_API_KEY','DATABASE_URL','REDIS_URL','KAFKA_BOOTSTRAP')),
 'provider_secret_file_absent':not Path('/run/sentinel/provider.env').exists(),'docker_socket_absent':not Path('/var/run/docker.sock').exists()}))
'''
    p=subprocess.run(command,input=program,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True)
    container=json.loads(p.stdout)
    result={'at':datetime.now(timezone.utc).isoformat(),'http_checks':checks,'container':container,
            'passed':all(x['passed'] for x in checks) and container['uid']!=0 and all(v for k,v in container.items() if k!='uid'),
            'scope':'Real public container boundary; no database/model capability or credentials. Local lab is a different service and was not attacked.'}
    target.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
