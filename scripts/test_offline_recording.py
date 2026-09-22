"""Verify the prepared public image without a network interface or credentials."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import uuid

ROOT=Path(__file__).resolve().parents[1]

def main():
    output=ROOT/'artifacts/phase5/offline-runtime.json'
    if output.exists():raise FileExistsError('Preserve previous offline proof')
    name='sentinel-offline-audit-'+uuid.uuid4().hex[:10]
    result={'started_at':datetime.now(timezone.utc).isoformat(),'scope':'Prepared image runtime offline; first image build/download is outside this guarantee.'}
    created=False
    try:
        p=subprocess.run(['docker','run','-d','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--tmpfs','/tmp:rw,noexec,nosuid,size=32m','project-sentinel:portfolio'],cwd=ROOT,capture_output=True,text=True,check=True)
        created=True
        program='''import json,os,time,urllib.request
def get(path):
 with urllib.request.urlopen('http://127.0.0.1:8000'+path,timeout=3) as r:return r.read()
end=time.monotonic()+25
while True:
 try:health=json.loads(get('/health'));break
 except Exception:
  if time.monotonic()>end:raise
  time.sleep(.25)
paths=['/','/replay.html','/evaluation.html','/architecture.html','/documentation.html','/portfolio.js','/documents.js','/portfolio.css','/replay.js','/favicon.svg','/docs/screenshots/dashboard.png','/api/portfolio/demo','/api/portfolio/evaluation','/api/portfolio/provenance','/api/portfolio/patch','/api/portfolio/docs?name=README.md','/api/portfolio/docs?name=FINAL_STATUS.md','/api/portfolio/docs?name=docs/pitch-30s.md']
checks=[{'path':p,'passed':bool(get(p))} for p in paths]
d=json.loads(get('/api/portfolio/demo'))
checks.extend({'path':'evidence/'+e['id'],'passed':json.loads(get('/api/portfolio/evidence/'+e['id']))['run_id']==d['run_id']} for e in d['evidence'])
print(json.dumps({'health':health,'checks':checks,'no_key':not os.getenv('LLM_API_KEY'),'no_env_file':not __import__('pathlib').Path('/app/.env').exists(),'run_id':d['run_id'],'passed':all(x['passed'] for x in checks) and not os.getenv('LLM_API_KEY') and not health['llm_enabled']}))
'''
        p=subprocess.run(['docker','exec','-i',name,'python','-'],input=program,capture_output=True,text=True,encoding='utf-8',check=True)
        result.update(json.loads(p.stdout))
        network=subprocess.check_output(['docker','inspect','--format','{{.HostConfig.NetworkMode}}',name],text=True).strip()
        result['network_mode']=network;result['passed']=result['passed'] and network=='none'
    except Exception as e:result.update(passed=False,error=str(e))
    finally:
        if created:result['cleanup_exit_code']=subprocess.run(['docker','rm','-f',name],capture_output=True).returncode
        result['finished_at']=datetime.now(timezone.utc).isoformat()
        with output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        print(json.dumps(result))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
