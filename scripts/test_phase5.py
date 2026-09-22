"""Run the local backend gate. Requires the local lab; never runs an LLM benchmark."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='backend-tests-local.json');a=p.parse_args()
    assert Path(a.output).name==a.output
    out=ROOT/'artifacts/phase5'/a.output
    if out.exists():raise FileExistsError('Choose a new test result filename')
    subprocess.run(['docker','compose','-f','compose.live.yaml','build','sentinel'],cwd=ROOT,check=True)
    command=['docker','compose','-f','compose.live.yaml','run','--rm','--no-deps','sentinel','python','-m','pytest','tests','-q','-p','no:cacheprovider']
    result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    out.parent.mkdir(exist_ok=True,parents=True)
    out.write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'exit_code':result.returncode,
        'command':command,'stdout':result.stdout,'stderr':result.stderr,'scope':'Local protocol, dependency, public API and boundary tests. No live model benchmark.'},indent=2),encoding='utf-8')
    print(result.stdout)
    raise SystemExit(result.returncode)
if __name__=='__main__':main()
