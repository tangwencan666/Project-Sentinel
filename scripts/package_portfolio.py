"""Create and verify a GitHub-candidate archive without credentials or internal outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',default='');parser.add_argument('--final',action='store_true');args=parser.parse_args()
    if args.final and args.release:raise ValueError('Use final or a release label')
    if args.release and not re.fullmatch('[a-z0-9-]{1,40}',args.release):raise ValueError('Invalid release label')
    suffix='-'+args.release if args.release else ''
    archive = ROOT / ('outputs/sentinel-portfolio-final.zip' if args.final else 'outputs/sentinel-phase5-portfolio'+suffix+'.zip')
    sidecar = ROOT / ('outputs/sentinel-portfolio-final.manifest.json' if args.final else 'outputs/sentinel-phase5-delivery'+suffix+'.json')
    if archive.exists() or sidecar.exists():
        raise FileExistsError('Preserve delivered artifacts; choose a new release before rebuilding')
    raw = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    names = sorted({n.decode('utf-8') for n in raw.split(b'\0') if n})
    if not names:
        raise ValueError('Empty Git publication tree')
    secrets = []
    if (ROOT / '.env').exists():
        for line in (ROOT / '.env').read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                value = value.strip().strip('\"').strip("'")
                if re.search('KEY|TOKEN|PASSWORD|SECRET', key, re.I) and len(value) >= 12:
                    secrets.append(value.encode())
    forbidden = {'evaluation', 'outputs', 'artifacts', 'node_modules', '__pycache__', '.git', '.idea', '.vscode', '.venv'}
    files = {}
    for name in names:
        p = ROOT / name
        if not p.is_file():
            continue
        if not p.resolve().is_relative_to(ROOT.resolve()) or p.is_symlink():
            raise ValueError('Unsafe path: ' + name)
        if forbidden.intersection(Path(name).parts) or (Path(name).name.startswith('.env') and Path(name).name != '.env.example'):
            raise ValueError('Prohibited publication path: ' + name)
        data = p.read_bytes()
        if len(data) > 25_000_000 or any(s in data for s in secrets):
            raise ValueError('Oversized or sensitive file: ' + name)
        if re.search(rb'(?:sk-[A-Za-z0-9]{24,}|Bearer [A-Za-z0-9._-]{24,})', data):
            raise ValueError('Credential-shaped content: ' + name)
        files[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name in files:
            data = (ROOT / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != files[name]['sha256']:
                raise RuntimeError('File changed during packaging: ' + name)
            z.writestr('project-sentinel/' + name, data)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:
            raise RuntimeError('Archive CRC failure')
        for name, meta in files.items():
            if hashlib.sha256(z.read('project-sentinel/' + name)).hexdigest() != meta['sha256']:
                raise RuntimeError('Archive hash mismatch: ' + name)
    result = {'archive': archive.name, 'bytes': archive.stat().st_size,
              'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'file_count': len(files), 'files': files, 'verified': True,
              'excluded': sorted(forbidden | {'.env'}),
              'scope': 'GitHub candidate source, genuine sanitized recordings, tests, docs and screenshots. No Git history or original private experiment archives.'}
    with sidecar.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}))


if __name__ == '__main__':
    main()
