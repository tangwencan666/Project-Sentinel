"""Verify the tested/running container actually contains the archived host source."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT='''import hashlib,json,sys
from pathlib import Path
expected=json.load(sys.stdin)
mismatches=[name for name,digest in expected.items() if not (Path('/app')/name).is_file() or hashlib.sha256((Path('/app')/name).read_bytes()).hexdigest()!=digest]
print(json.dumps({'verified_files':len(expected),'mismatches':mismatches}))
sys.exit(86 if mismatches else 0)
'''

def verify(hashes,running=False):
    files={name:digest for name,digest in hashes.items() if name.startswith(('sentinel/','services/','tests/','requirements.'))}
    command=['docker','compose',*(['exec','-T'] if running else ['run','--rm','--no-deps','-T']),'sentinel','python','-c',SCRIPT]
    run=subprocess.run(command,input=json.dumps(files),capture_output=True,text=True,cwd=ROOT,timeout=60)
    if run.returncode: raise RuntimeError('Runtime source verification failed: '+run.stdout+run.stderr)
    result=json.loads(run.stdout)
    result['scope']='Exact application/test/dependency file hashes in '+('running container' if running else 'test image')
    return result
