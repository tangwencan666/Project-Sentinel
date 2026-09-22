"""Append-only historical baseline and benchmark seal. Never regenerate V1."""
import hashlib
import json
from pathlib import Path
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'evaluation/baselines'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def exclusive(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise RuntimeError(f'Frozen artifact mismatch: {path.name}')
        return
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(stat.S_IREAD)

def main():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    for name, digest in manifest['file_hashes'].items():
        assert sha(BASE / name) == digest, name
    aliases = {'rule.json': BASE / 'v1-rule-based.json',
               'v2-hybrid.json': ROOT / 'evaluation/results/v2-hybrid-validated.json',
               'v3-context.json': ROOT / 'evaluation/results/v3-context-optimized-validated.json'}
    for name, source in aliases.items():
        exclusive(BASE / name, source.read_bytes())
    files = ['rule.json', 'v1-pure-llm.json', 'v2-hybrid.json', 'v3-context.json', 'manifest.json', 'archive.zip']
    exclusive(BASE / 'manifest.sha256', ''.join(f'{sha(BASE / name)}  {name}\n' for name in files).encode())
    benchmark = ROOT / 'evaluation/benchmarks/sentinel-benchmark-v1'
    benchmark.mkdir(parents=True, exist_ok=True)
    protected = ['sentinel/scenarios.py', 'sentinel/evaluator.py', 'services/app.py',
                 'services/pricing.py', 'services/runtime.py', 'services/loadgen.py',
                 'tests/pricing_contract.py', 'infra/init.sql']
    for name in protected:
        target = benchmark / name.replace('/', '__')
        exclusive(target, (ROOT / name).read_bytes())
    version = {'benchmark_id': 'sentinel-benchmark-v1', 'ground_truth_version': 'sentinel-ground-truth-v1',
               'protected_sha256': {name: sha(ROOT / name) for name in protected},
               'history': 'V2/V3 select the previously declared first VALID pool trial; original invalid-fixture trials and all semantic failures remain in evaluation/results.',
               'immutability': 'Exclusive writes + SHA256 + read-only files; not administrator-proof WORM storage.'}
    exclusive(benchmark / 'manifest.json', (json.dumps(version, indent=2) + '\n').encode())
    print(json.dumps({'status': 'sealed', 'baseline_count': 4, 'benchmark_id': version['benchmark_id'],
                      'v1_manifest_sha256': sha(BASE / 'manifest.json')}))

if __name__ == '__main__':
    main()
