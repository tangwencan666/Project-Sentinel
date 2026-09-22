"""Real provider + container restart check; separate from the eight accuracy trials."""
import json
import argparse
from pathlib import Path
import subprocess
import time
from evaluate_phase2 import api

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--incident');parser.add_argument('--output',default='evaluation/resume-live.json');parser.add_argument('--mode',choices=['HYBRID_V2','HYBRID_V3'],default='HYBRID_V2');args=parser.parse_args()
output=ROOT/args.output
if output.exists(): raise FileExistsError('retain earlier restart test')
for _ in range(30):
    try: api('/incidents');break
    except Exception: time.sleep(1)
api('/evaluation-session/true','POST');api('/recover','POST')
provider=api('/provider/check','POST')
if provider['status']!='available': raise RuntimeError('real provider unavailable')
iid=args.incident or api('/incidents','POST',{'mode':args.mode,'controlled_recovery':False})['id']
if args.incident and api('/incidents/'+iid)['status']=='failed':
    api('/incidents/'+iid+'/resume','POST');time.sleep(2)
record={'incident_id':iid,'mode':args.mode,'scope':'operational workload resume test, not an accuracy trial; all earlier failed restart preflights retained','provider':provider}
print(json.dumps({'restart_test_incident':iid}),flush=True)
for _ in range(90):
    data=api('/incidents/'+iid);context=api('/incidents/'+iid+'/context')
    cp=context.get('checkpoint') or {}
    if cp.get('phase')=='INVESTIGATING':
        before=api('/incidents/'+iid+'/agent');record['before_run_id']=before['run_id']
        record['before_evidence_ids']=[e['id'] for e in before['evidence']]
        record['checkpoint_before']=cp
        subprocess.run(['docker','compose','restart','sentinel'],cwd=ROOT,check=True,timeout=35)
        break
    if data['status']=='failed':
        record.update(passed=False,status='failed',failure_stage='before_restart',ledger=api('/incidents/'+iid+'/agent'),steps=data['steps'],final_checkpoint=cp)
        with output.open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
        api('/evaluation-session/false','POST')
        raise RuntimeError('resume preflight failed before restart; original record saved')
    time.sleep(1)
else: raise RuntimeError('no investigation checkpoint observed')
for _ in range(160):
    time.sleep(2)
    try: data=api('/incidents/'+iid)
    except Exception: continue
    if data['status'] not in ('detected','investigating','awaiting_recovery'): break
after=api('/incidents/'+iid+'/agent')
record.update(after_run_id=after['run_id'],status=data['status'],
    same_run=after['run_id']==record['before_run_id'],
    original_evidence_preserved=set(record['before_evidence_ids']).issubset({e['id'] for e in after['evidence']}),
    resume_events=[s for s in data['steps'] if s['kind']=='Investigation Resumed'],
    final_checkpoint=api('/incidents/'+iid+'/context')['checkpoint'],ledger=after,steps=data['steps'])
record['passed']=record['same_run'] and record['original_evidence_preserved'] and bool(record['resume_events']) and record['final_checkpoint']['phase']=='COMPLETED'
output.parent.mkdir(parents=True,exist_ok=True)
with output.open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
print(json.dumps({k:v for k,v in record.items() if k in ('passed','same_run','original_evidence_preserved','status','final_checkpoint')}),flush=True)
api('/evaluation-session/false','POST')
if not record['passed']: raise SystemExit(1)
