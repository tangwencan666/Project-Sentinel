"""Test the GitHub publication tree without .env or model credentials, on an isolated Compose project."""
import argparse
from datetime import datetime,timezone
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',default='');args=parser.parse_args()
    if args.release and not re.fullmatch('[a-z0-9-]{1,40}',args.release):raise ValueError('Invalid release label')
    suffix='-'+args.release if args.release else ''
    stage=ROOT/('outputs/phase5-cleanstart'+suffix);stage.mkdir(parents=True,exist_ok=False)
    names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
    for raw in names:
        if not raw:continue
        name=raw.decode();source=ROOT/name;dest=stage/name
        if not source.is_file():continue
        assert source.resolve().is_relative_to(ROOT.resolve()) and dest.resolve().is_relative_to(stage.resolve())
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    assert not (stage/'.env').exists()
    env={k:v for k,v in os.environ.items() if not k.startswith(('LLM_','DATABASE_','REDIS_','KAFKA_'))}
    env.update(DEMO_PORT='18084',DEMO_ALLOWED_HOSTS='localhost,127.0.0.1,sentinel-demo')
    cmd=['docker','compose','-p','sentinel-cleanstart'+suffix,'-f',str(stage/'compose.yaml')]
    result={'started_at':datetime.now(timezone.utc).isoformat(),'source':'Git candidate tree, .env absent','live_llm_calls':0}
    try:
        p=subprocess.run([*cmd,'up','-d','--build','--wait'],cwd=stage,env=env,capture_output=True,text=True,encoding='utf-8',timeout=240)
        result.update(build_exit_code=p.returncode,build_output=p.stdout,build_stderr=p.stderr)
        p.check_returncode()
        def get(path):
            with urllib.request.urlopen('http://127.0.0.1:18084'+path,timeout=15) as r:return json.load(r)
        result['health']=get('/health');result['config']=get('/api/portfolio/config')
        d=get('/api/portfolio/demo');result['recorded_run_id']=d['run_id']
        result['passed']=result['health']['llm_enabled'] is False and result['config']['public_demo'] and d['run_id']=='759044e6-c016-489b-a459-137ca4846462'
    except Exception as exc:result.update(passed=False,error=type(exc).__name__+': '+str(exc))
    finally:
        p=subprocess.run([*cmd,'down'],cwd=stage,env=env,capture_output=True,text=True,encoding='utf-8',timeout=60)
        result['cleanup_exit_code']=p.returncode;result['finished_at']=datetime.now(timezone.utc).isoformat()
        target=ROOT/('artifacts/phase5/clean-start'+(suffix or '-first')+'.json')
        with target.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        print(json.dumps({k:v for k,v in result.items() if k not in ('build_output','build_stderr')}))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
