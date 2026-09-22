"""SIGKILL an owned, isolated runtime container and resume the same real-model run."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import time
import uuid
from evaluate_phase2 import api
from evaluate_phase3 import source_manifest
from runtime_source_gate import verify
ROOT=Path(__file__).resolve().parents[1]

def docker(*args):
    p=subprocess.run(['docker',*args],cwd=ROOT,text=True,encoding='utf-8',capture_output=True,timeout=60)
    if p.returncode: raise RuntimeError(p.stderr)
    return p.stdout.strip()

def events(name):
    rows=[]
    for line in docker('logs',name).splitlines():
        try: value=json.loads(line)
        except ValueError: continue
        if value.get('event') in ('READY_FOR_SIGKILL','RESTORED_BEFORE_RESUME','RESUME_FINISHED'): rows.append(value)
    return rows

def wait_event(name,event,timeout):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        rows=events(name)
        if any(r['event']==event for r in rows): return next(r for r in rows if r['event']==event)
        state=json.loads(docker('inspect','--format','{{json .State}}',name))
        if state['Status']=='exited': raise RuntimeError(f'Worker exited before {event}: '+str(state['ExitCode'])+' '+docker('logs',name)[-5000:])
        time.sleep(2)
    raise TimeoutError(event)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tests',required=True);parser.add_argument('--output',default='crash-resume-first.json');args=parser.parse_args()
    assert Path(args.output).name==args.output and Path(args.tests).name==args.tests
    hashes=source_manifest();tests=json.loads((ROOT/'evaluation/phase4'/args.tests).read_text(encoding='utf-8'))
    assert tests['exit_code']==0 and hashes==tests['source_sha256']
    proof=verify(hashes)
    output=ROOT/'evaluation/phase4'/args.output
    record={'scope':'REAL_DEEPSEEK_SIGKILL_RECOVERY_NOT_RCA_BENCHMARK','started_at':datetime.now(timezone.utc).isoformat(),
        'source_sha256':hashes,'container_source_verification':proof,'passed':False,'completed':False,
        'injected_error_origin':'RecoveryTestController invokes a real absent-symbol tool after a model-created hypothesis; this is not an attributed model mistake.'}
    with output.open('x',encoding='utf-8') as f: json.dump(record,f)
    names=[]
    def save(): output.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    def start(stage,*extra):
        name='sentinel-phase4-recovery-'+stage+'-'+uuid.uuid4().hex[:10];names.append(name)
        docker('compose','run','-d','--no-deps','--name',name,'-T','sentinel','python','-u','tests/recovery_worker.py',stage,*extra)
        return name
    api('/evaluation-session/true','POST')
    try:
        api('/recover','POST');api('/traffic/true','POST');time.sleep(25)
        queue_before=api('/evidence/queue');time.sleep(3);queue_after=api('/evidence/queue')
        assert queue_after and all(r['lag']<=5 for r in queue_after)
        assert sum(r['committed_offset'] for r in queue_after)>sum(r['committed_offset'] for r in queue_before)
        record['healthy_consumer_proof']={'before':queue_before,'after':queue_after}
        api('/faults/code_exception','POST',{'duration_seconds':600});time.sleep(24)
        name=start('start');record['start_container']=name;save()
        ready=wait_event(name,'READY_FOR_SIGKILL',400);record['before_kill']=ready;save()
        assert all(ready['fields'][k] for k in ('active_hypotheses','validation_errors','critical_evidence'))
        labels=json.loads(docker('inspect','--format','{{json .Config.Labels}}',name))
        assert labels['com.docker.compose.project']=='project-sentinel' and name in names
        docker('kill','--signal','KILL',name)
        record['killed_state']=json.loads(docker('inspect','--format','{{json .State}}',name));save()
        assert record['killed_state']['ExitCode']==137
        resumed=start('resume',ready['fields']['run_id']);record['resume_container']=resumed;save()
        restored=wait_event(resumed,'RESTORED_BEFORE_RESUME',30);record['restored']=restored
        assert restored['sha256']==ready['sha256'],'Restored checkpoint differs'
        record['state_restored_exactly']=True;save()
        result=wait_event(resumed,'RESUME_FINISHED',520);record['result']=result
        record['completed']=True;record['passed']=result['run']['status']=='completed' and result['resume_count']==1
    except Exception as exc:
        record['error']=str(exc)
        for name in names:
            try: record.setdefault('worker_events',{})[name]=events(name)
            except Exception: pass
    finally:
        record['finished_at']=datetime.now(timezone.utc).isoformat();save();output.chmod(0o444)
        for name in names:
            try:
                state=json.loads(docker('inspect','--format','{{json .State}}',name))
                if state['Running']: docker('stop','--time','5',name)
            except Exception: pass
        api('/recover','POST');api('/evaluation-session/false','POST')
    print(json.dumps({'passed':record['passed'],'state_restored_exactly':record.get('state_restored_exactly'),
        'run':record.get('result',{}).get('run'),'error':record.get('error')},ensure_ascii=False))
    if not record['passed']: raise SystemExit(1)
if __name__=='__main__': main()
