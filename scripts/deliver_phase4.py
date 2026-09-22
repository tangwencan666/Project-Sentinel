"""Package source + actual evidence after the first final suite, without credentials or overwrites."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import zipfile
from evaluate_phase3 import source_manifest
ROOT=Path(__file__).resolve().parents[1]

def main():
    suite=json.loads((ROOT/'evaluation/results/v4.1-first-controlled.json').read_text(encoding='utf-8'))
    assert suite['completed'] and len(suite['results'])==8
    assert suite['source_sha256']==source_manifest(),'Runtime changed after first release evaluation'
    for proof in ('reliability-tests-final.json','static-audit-final.json','adversarial-audit-final.json',
                  'crash-resume-followup.json','ui-e2e-final.json','live-browser-first.json',
                  'release-browser-first.json','release-health-first.json'):
        data=json.loads((ROOT/'evaluation/phase4'/proof).read_text(encoding='utf-8'))
        assert data.get('passed',data.get('exit_code')==0),proof
    config={}
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1);config[key.strip()]=value.strip().strip('"').strip("'")
    secret=config.get('LLM_API_KEY','').encode();assert secret
    files=[]
    for folder in ('services','sentinel','tests','scripts','web','infra','docs','evaluation'):
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pending'))
    for name in ('README.md','Dockerfile','compose.yaml','requirements.txt','requirements.lock','.dockerignore','.gitignore','.env.example'):
        if (ROOT/name).exists():files.append(ROOT/name)
    manifest={}
    for file in sorted(set(files)):
        assert file.name!='.env' and file.resolve().is_relative_to(ROOT.resolve())
        content=file.read_bytes()
        if secret in content: raise RuntimeError('Configured key found; packaging stopped without printing its value')
        manifest[file.relative_to(ROOT).as_posix()]={'sha256':hashlib.sha256(content).hexdigest(),'bytes':len(content)}
    output=ROOT/'outputs';output.mkdir(exist_ok=True)
    archive=output/'sentinel-phase4-source-evidence.zip'
    report=json.loads((ROOT/'evaluation/phase4/final-release-report.json').read_text(encoding='utf-8'))
    assert report['status']=='completed' and len(report['version']['results'])==8
    proof={'created_at':datetime.now(timezone.utc).isoformat(),'benchmark_id':suite['benchmark_id'],
        'formal_result':'evaluation/results/v4.1-first-controlled.json','files':manifest,
        'release_metrics':report['version']['metrics'],
        'exclusions':['.env','Git internals','bytecode','Docker volumes/images','prior delivery output archives'],
        'credential_scan':'Literal configured key checked without exporting its value; nested historical archives also scanned by the static audit.'}
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in manifest:z.write(ROOT/name,name)
        z.writestr('DELIVERY-MANIFEST.json',json.dumps(proof,ensure_ascii=False,indent=2))
    proof.update(archive=archive.name,archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),archive_bytes=archive.stat().st_size)
    with (output/'sentinel-phase4-delivery.json').open('x',encoding='utf-8') as f:json.dump(proof,f,ensure_ascii=False,indent=2)
    archive.chmod(0o444);(output/'sentinel-phase4-delivery.json').chmod(0o444)
    print(json.dumps({'archive':str(archive),'sha256':proof['archive_sha256'],'files':len(manifest),'bytes':proof['archive_bytes']}))
if __name__=='__main__':main()
