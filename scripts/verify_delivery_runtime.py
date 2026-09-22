"""Compare deployed sources and final live health without reading container secrets."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
import subprocess
from evaluate_phase2 import api

ROOT=Path(__file__).resolve().parents[1]
program="""from pathlib import Path
import hashlib,json
paths=[p for d in ('sentinel','services','tests','web') for p in Path(d).glob('*') if p.suffix in ('.py','.js','.css','.html')]
print(json.dumps({p.as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))
"""
runtime=json.loads(subprocess.check_output(['docker','compose','exec','-T','sentinel','python','-c',program],cwd=ROOT,text=True))
different=[p for p,h in runtime.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
ps=subprocess.check_output(['docker','compose','ps','--format','json'],cwd=ROOT,text=True,encoding='utf-8')
containers=[{k:c.get(k) for k in ('Service','State','Health','Image')} for c in map(json.loads,ps.splitlines())]
summary=api('/overview');measured=api('/measured')
lock=subprocess.check_output(['docker','compose','exec','-T','redis','redis-cli','EXISTS','control:evaluation_lock'],cwd=ROOT,text=True).strip()
image=subprocess.check_output(['docker','inspect','--format','{{.Image}}','project-sentinel-sentinel-1'],text=True).strip()
passed=not different and len(containers)==14 and all(c['State']=='running' and c['Health'] in ('','healthy',None) for c in containers) and not summary['active_faults'] and summary['traffic_enabled'] and lock=='0' and all(float(h['error_pct'])==0 for h in measured['http'])
record={'at':datetime.now(timezone.utc).isoformat(),'passed':passed,'image':image,'runtime_source_sha256':runtime,'mismatches':different,
    'containers':containers,'active_faults':summary['active_faults'],'traffic_enabled':summary['traffic_enabled'],'evaluation_lock_exists':lock=='1','measured':measured,
    'scope':'Current delivery runtime. Exact benchmark image and sources are separately retained in runtime-manifest.json and frozen-framework.zip.'}
(ROOT/'evaluation/delivery-runtime.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'passed':passed,'source_files':len(runtime),'mismatches':different,'containers':len(containers),'active_faults':summary['active_faults'],'traffic_enabled':summary['traffic_enabled'],'evaluation_lock_exists':lock=='1'}))
if not passed:raise SystemExit(1)
