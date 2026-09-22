"""Capture a real-provider component qualification before another fault suite."""
import json
from pathlib import Path
import subprocess
import argparse

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--output',default='field-repair-provider-probe.json');args=parser.parse_args()
assert Path(args.output).name==args.output
path=root/'evaluation/phase4'/args.output
if path.exists(): raise FileExistsError('Probe result is immutable; do not overwrite failed probes')
command=['docker','compose','run','--rm','--no-deps','-v',str(root/'scripts/phase4_candidates')+':/candidates:ro',
         'sentinel','python','/candidates/probe_long_fields.py']
run=subprocess.run(command,cwd=root,capture_output=True,text=True,encoding='utf-8',timeout=300)
result=json.loads(run.stdout) if run.returncode==0 else {'passed':False,'error':run.stderr,'stdout':run.stdout}
result['command']=command;result['exit_code']=run.returncode
with path.open('x',encoding='utf-8') as output: json.dump(result,output,ensure_ascii=False,indent=2)
path.chmod(0o444)
print(json.dumps({'passed':result['passed'],'cases':[{'case':r['case_label'],'passed':r['passed'],'attempts':len(r['attempts'])} for r in result.get('cases',[])]}))
if not result['passed']: raise SystemExit(1)
