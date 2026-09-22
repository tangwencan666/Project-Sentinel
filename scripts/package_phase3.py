"""Create an auditable local delivery bundle; never include .env or runtime volumes."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    paths=[]
    for directory in ('sentinel','services','infra','tests','web','docs','scripts','evaluation'):
        paths += [p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pending')]
    paths += [ROOT/name for name in ('README.md','Dockerfile','compose.yaml','requirements.txt','requirements.lock','.env.example','.gitignore','.dockerignore')]
    names=[p.relative_to(ROOT).as_posix() for p in paths]
    assert all(Path(n).name!='.env' for n in names)
    # Enforce the configured secret exclusion, including uncompressed archived source members.
    secret=None
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1)
            if key.strip()=='LLM_API_KEY': secret=value.strip().strip('"').strip("'").encode()
    if not secret: raise RuntimeError('configured secret is required for packaging scan')
    for p in paths:
        if secret in p.read_bytes(): raise RuntimeError('secret detected; bundle refused')
        if p.suffix=='.zip':
            with zipfile.ZipFile(p) as archive:
                if any(secret in archive.read(n) for n in archive.namelist()): raise RuntimeError('secret detected in archive; bundle refused')
    manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in paths: archive.write(p,p.relative_to(ROOT).as_posix())
        archive.writestr('DELIVERY-MANIFEST.json',json.dumps({'sha256':manifest,'excluded':['.env','runtime volumes','__pycache__'],'scope':'Local source and evidence snapshot; no public publishing.'},indent=2))
    print(json.dumps({'bundle':str(args.output.resolve()),'files':len(paths),'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest(),'bytes':args.output.stat().st_size}))


if __name__=='__main__': main()
