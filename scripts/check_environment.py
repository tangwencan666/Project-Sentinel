"""Friendly read-only environment validation. Never sends a provider request or prints credentials."""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['recorded','live'],default='recorded');parser.add_argument('--port',type=int);args=parser.parse_args()
    port=args.port or (18082 if args.mode=='recorded' else 18083);checks=[]
    def note(name,ok,message):
        checks.append({'name':name,'passed':ok,'message':message});print(f"[{'OK' if ok else 'CHECK'}] {name}: {message}")
    for name,cmd in [('Docker',['docker','info','--format','{{.ServerVersion}}']),('Compose',['docker','compose','version','--short'])]:
        try:
            p=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=15)
            note(name,p.returncode==0,p.stdout.strip() if p.returncode==0 else 'Unavailable; start Docker Desktop / Engine.')
        except (OSError,subprocess.TimeoutExpired):note(name,False,'Not installed, not running, or timed out.')
    config={};env=ROOT/'.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1);config[k.strip()]=v.strip().strip('"').strip("'")
    note('.env',args.mode=='recorded' or env.exists(),'Optional for recorded mode; credentials not required.' if args.mode=='recorded' else 'Present.' if env.exists() else 'Copy .env.example to .env.')
    note('LLM provider',args.mode=='recorded' or all(config.get(k) for k in ('LLM_MODEL','LLM_API_KEY','LLM_BASE_URL')),
         'Disabled; no model call made.' if args.mode=='recorded' else 'Configuration presence only; no paid connectivity probe.')
    def get(path):
        with urllib.request.urlopen(f'http://127.0.0.1:{port}'+path,timeout=15) as r:return json.load(r)
    try:
        h=get('/health');note('Port / API',True,f'Port {port} serves Sentinel: '+h.get('mode',h.get('status','responding')))
        c=get('/api/portfolio/config');note('Mode boundary',c['public_demo'] if args.mode=='recorded' else not c['public_demo'],'Public read-only.' if c['public_demo'] else 'Local Live workspace; AI enabled: '+str(c['live_enabled']))
        if args.mode=='recorded':
            d=get('/api/portfolio/demo');note('Recorded run',bool(d.get('events')) and not d['live'],'Genuine frozen run '+d['run_id'])
            for dep in ('Database','Redis','Kafka'):note(dep,True,'Not required / not connected in recorded mode.')
        else:
            for dep,route in [('Database','database'),('Redis','cache'),('Kafka','queue')]:
                try:note(dep,bool(get('/api/evidence/'+route)),'Read-only observation retrieved.')
                except Exception:note(dep,False,'Observation unavailable; inspect local Compose health.')
    except Exception:
        with socket.socket() as sock:occupied=sock.connect_ex(('127.0.0.1',port))==0
        note('Port / API',False,f'Port {port} '+('is occupied but the expected API is unavailable.' if occupied else 'is free; start the matching Compose stack.'))
    report={'mode':args.mode,'checks':checks,'passed':all(c['passed'] for c in checks),'live_llm_calls':0}
    print(json.dumps(report,ensure_ascii=True))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
