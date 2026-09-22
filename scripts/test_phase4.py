"""Run the phase C gate and retain exact test output and tested source hashes."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import argparse
from evaluate_phase3 import source_manifest
from runtime_source_gate import verify

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='reliability-tests.json');args=parser.parse_args()
    hashes=source_manifest();proof=verify(hashes)
    command=['docker','compose','run','--rm','--no-deps','sentinel','python','-m','pytest',
        *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'tests').glob('test_*.py'))],'-q','-p','no:cacheprovider']
    result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
    report={'at':datetime.now(timezone.utc).isoformat(),'command':command,'exit_code':result.returncode,
            'output':result.stdout,'stderr':result.stderr,'source_sha256':hashes,'container_source_verification':proof,
            'scope':'Protocol boundary/reliability tests using actual PostgreSQL/Redis/local HTTP, not diagnosis accuracy.'}
    folder=ROOT/'evaluation/phase4';folder.mkdir(exist_ok=True)
    assert source_manifest()==hashes,'Source changed while tests were running'
    assert Path(args.output).name==args.output
    (folder/args.output).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(result.stdout);raise SystemExit(result.returncode)
if __name__=='__main__': main()
