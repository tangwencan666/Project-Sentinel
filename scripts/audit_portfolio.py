"""Repository-wide exact-secret/archive/history audit and GitHub publication checks. Never prints secret values."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def git(*args,input=None):
    return subprocess.run(['git',*args],cwd=ROOT,input=input,capture_output=True,check=True).stdout

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='repository-audit-first.json');args=parser.parse_args()
    out=ROOT/'artifacts/phase5'/args.output
    if out.exists():raise FileExistsError('Retain prior audit')
    secrets=[]
    if (ROOT/'.env').exists():
        for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                k,v=line.split('=',1);v=v.strip().strip('"').strip("'")
                if re.search('KEY|TOKEN|PASSWORD|SECRET',k,re.I) and len(v)>=12:secrets.append(v.encode())
    leaks=[];archive_violations=[];scanned=0;archives=0;patterns=[]
    token=re.compile(rb'(?:sk-[A-Za-z0-9]{24,}|Bearer [A-Za-z0-9._-]{24,})')
    def scan(name,data,depth=0):
        nonlocal scanned,archives
        scanned+=1
        if any(s in data for s in secrets):leaks.append(name)
        if token.search(data):patterns.append(name)
        if name.endswith('.zip') and depth<4:
            archives+=1
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for entry in z.infolist():
                    if entry.is_dir():continue
                    if Path(entry.filename).name=='.env':archive_violations.append(name+'!'+entry.filename)
                    scan(name+'!'+entry.filename,z.read(entry),depth+1)
    for p in ROOT.rglob('*'):
        if not p.is_file() or any(x in p.parts for x in ('.git','node_modules','.venv','__pycache__','.pytest_cache')) or p.name=='.env':continue
        scan(p.relative_to(ROOT).as_posix(),p.read_bytes())
    commits=git('rev-list','--all').splitlines()
    history_blobs=0
    for row in git('rev-list','--objects','--all').splitlines():
        oid=row.split(b' ',1)[0].decode()
        if git('cat-file','-t',oid).strip()==b'blob':
            scan('git-history:'+oid,git('cat-file','blob',oid));history_blobs+=1
    candidates=[p.decode('utf-8') for p in git('ls-files','--cached','--others','--exclude-standard','-z').split(b'\0') if p]
    prohibited=[p for p in candidates if Path(p).name=='.env' or any(x in Path(p).parts for x in ('node_modules','__pycache__','.idea','.vscode','evaluation','outputs','artifacts'))]
    large=[{'path':p,'bytes':(ROOT/p).stat().st_size} for p in candidates if (ROOT/p).is_file() and (ROOT/p).stat().st_size>25_000_000]
    absolute=[];broken=[]
    for p in [ROOT/'README.md',ROOT/'FINAL_STATUS.md',*(ROOT/'docs').rglob('*.md'),*(ROOT/'web').glob('*')]:
        if not p.exists():continue
        if p.suffix not in ('.md','.html','.js','.css'):continue
        text=p.read_text(encoding='utf-8')
        if re.search(r'(?:[A-Z]:[\\/]project\d+|[A-Z]:[\\/]Users[\\/])',text,re.I):absolute.append(p.relative_to(ROOT).as_posix())
        if p.suffix=='.md':
            for link in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text):
                target=link.strip('<>').split('#',1)[0]
                if not target or re.match(r'\w+://',target):continue
                resolved=(p.parent/target).resolve()
                if not resolved.exists():broken.append({'file':p.relative_to(ROOT).as_posix(),'target':target})
    seals={'evaluation/results/v4.1-first-controlled.json':'74b48f0cc7a3f341ca0a088a50054fa0c45209034d12aa4f5de46a4f1fa2c81a',
           'evaluation/results/v3.1-first-controlled.json':'f8c2818edec2c1c521571a09c0193c4e1f50dfc96a5ea724057df09749c768cf',
           'evaluation/results/v4-first-controlled.json':'454f2181cdb6a26111bc1b3c49e2259da5c76a1910dc1dc342a935d330658faa'}
    integrity={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in seals.items() if (ROOT/p).exists()}
    baseline=ROOT/'evaluation/baselines/manifest.sha256'
    if baseline.exists():
        for line in baseline.read_text().splitlines():
            h,p=line.split('  ',1);integrity['baseline/'+p]=hashlib.sha256((baseline.parent/p).read_bytes()).hexdigest()==h
    result={'at':datetime.now(timezone.utc).isoformat(),'passed':not any((leaks,archive_violations,prohibited,large,absolute,broken,patterns)) and all(integrity.values()),
      'files_and_archive_entries_scanned':scanned,'archives_including_nested':archives,'exact_configured_secret_matches':leaks,
      'suspicious_token_pattern_files':sorted(set(patterns)),'unsafe_archive_entries':archive_violations,
      'git_commit_count':len(commits),'git_history_blobs_scanned':history_blobs,'github_candidate_count':len(candidates),
      'prohibited_git_candidates':prohibited,'oversized_git_candidates':large,'personal_paths_in_public_text':absolute,'broken_relative_links':broken,'frozen_integrity':integrity,
      'reviewed_lab_credentials':'compose.live.yaml / infra SQL contain explicitly local sentinel demo credentials; public image excludes these services and credentials. Not production secrets.',
      'scope':'Literal configured secrets plus credential-shaped tokens across current files, nested archives and Git history. No claim to detect all encoded/semantic secrets. .env is intentionally local and Git-ignored.'}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
