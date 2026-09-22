"""Real serial fault evaluation. No model responses, evidence, or metrics are fabricated."""
import argparse
import sys
import json
import time
import urllib.request
import urllib.error
import http.client
from pathlib import Path
from datetime import datetime,timezone

if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
BASE='http://127.0.0.1:18082/api'
def api(path,method='GET',body=None):
    req=urllib.request.Request(BASE+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as response: return json.load(response)

def wait_incident(iid,controlled_recovery=False):
    previous=None
    for _ in range(130):
        data=api('/incidents/'+iid)
        if data['status']!=previous:
            print(json.dumps({'incident_id':iid,'status':data['status']},ensure_ascii=False),flush=True);previous=data['status']
        if data['status']=='awaiting_recovery' and controlled_recovery:
            api('/recover','POST');time.sleep(24)
            api('/incidents/'+iid+'/recovery-measurement','POST',{'run_id':data['investigation_run']})
        elif data['status'] not in ('detected','investigating','verifying','awaiting_recovery') and data.get('investigation_run'): return data
        time.sleep(5)
    raise TimeoutError('investigation did not terminate within runner budget')

def aggregates(results):
    out={}
    for mode in ('RULE_BASED','AI'):
        rows=[r for r in results if r.get('mode')==mode]
        patches=[r for r in rows if r.get('patch_requested') or r.get('patch_generated')]
        out[mode]={'scenarios':len(rows),'root_cause_correct':sum(r.get('judgment',{}).get('root_cause_correct',False) for r in rows),'root_cause_accuracy':sum(r.get('judgment',{}).get('root_cause_correct',False) for r in rows)/len(rows) if rows else None,'service_accuracy':sum(r.get('service_correct',False) for r in rows)/len(rows) if rows else None,'patch_success_rate':sum(r.get('fault_replay_passed',False) for r in patches)/len(patches) if patches else None,'patch_denominator':len(patches),'average_tool_calls':sum(r.get('tool_calls',0) for r in rows)/len(rows) if rows else None,'average_duration_seconds':sum(r.get('duration_seconds',0) for r in rows)/len(rows) if rows else None,'evidence_quality':sum(r.get('judgment',{}).get('evidence_quality',0) for r in rows)/len(rows) if rows else None}
    return out

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scenarios',nargs='*');parser.add_argument('--modes',nargs='+',default=['RULE_BASED','AI']);parser.add_argument('--output',default='docs/phase2-evaluation.json');parser.add_argument('--controlled-recovery',action='store_true');args=parser.parse_args()
    for attempt in range(30):
        try:
            known=[s['scenario_id'] for s in api('/scenarios')];break
        except (OSError,http.client.HTTPException): time.sleep(1)
    else: raise RuntimeError('Sentinel did not become ready')
    selected=args.scenarios or known
    if any(s not in known for s in selected): raise ValueError('unknown scenario')
    provider=api('/provider')
    if 'AI' in args.modes and provider['status']!='available':
        provider=api('/provider/check','POST')
        if provider['status']!='available': raise RuntimeError('Provider unavailable; no silent baseline fallback')
    results=[];path=Path(args.output)
    def save():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'model':provider.get('model'),'results':results,'aggregates':aggregates(results),'provider_usage':api('/provider')['usage']},ensure_ascii=False,indent=2),encoding='utf-8')
    api('/evaluation-session/true','POST')
    try:
        api('/traffic/true','POST')
        for scenario in selected:
            api('/recover','POST');time.sleep(22)
            before=api('/measured')
            api('/faults/'+scenario,'POST',{'duration_seconds':600});time.sleep(24)
            during=api('/measured');scenario_results=[];previous_recovered=False
            for mode in args.modes:
                # Model receives only an incident built from observed telemetry, never the scenario ID.
                # Each mode gets a fresh fault window if the preceding mode performed recovery.
                if mode!=args.modes[0]:
                    api('/faults/'+scenario,'POST',{'duration_seconds':600})
                    if previous_recovered: time.sleep(24)
                iid=api('/incidents','POST',{'mode':mode,'controlled_recovery':args.controlled_recovery and mode=='AI'})['id']
                print(json.dumps({'scenario':scenario,'mode':mode,'incident_id':iid},ensure_ascii=False),flush=True)
                try:
                    finished=wait_incident(iid,args.controlled_recovery and mode=='AI')
                    previous_recovered=bool((finished.get('report') or {}).get('measured_recovery'))
                    result=api('/incidents/'+iid+'/evaluate','POST',{'scenario_id':scenario})
                    result['measured']={'before':before,'fault_active':during,'after':None,'recovery_actor':'operator_experiment_runner','not_an_ai_repair':True}
                    results.append(result)
                    scenario_results.append(result)
                    print(json.dumps({'scenario':scenario,'mode':mode,'correct':result['judgment']['root_cause_correct'],'critic':(result.get('critic') or {}).get('verdict'),'patches':result['patches']},ensure_ascii=True),flush=True)
                except Exception as exc:
                    results.append({'scenario':scenario,'mode':mode,'incident_id':iid,'error':type(exc).__name__+': '+str(exc),'judgment':{'root_cause_correct':False},'service_correct':False})
                    print(json.dumps({'scenario':scenario,'mode':mode,'failure':str(exc)},ensure_ascii=False),flush=True)
                save()
            api('/recover','POST');time.sleep(22)
            after=api('/measured')
            for result in scenario_results: result['measured']['after']=after
            save()
    finally:
        api('/recover','POST');api('/evaluation-session/false','POST');save()

if __name__=='__main__': main()
