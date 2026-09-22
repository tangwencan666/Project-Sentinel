"""Version the phase G/H business extraction and readiness changes without rewriting v1."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]

def main():
    old=ROOT/'evaluation/benchmarks/sentinel-benchmark-v1'
    manifest=json.loads((old/'manifest.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(old/'business-source.zip') as z:
        for path,digest in manifest['protected_sha256'].items():
            assert hashlib.sha256(z.read(path)).hexdigest()==digest,path
    unchanged=['sentinel/scenarios.py','sentinel/evaluator.py','services/pricing.py','services/loadgen.py','tests/pricing_contract.py','infra/init.sql']
    for path in unchanged: assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==manifest['protected_sha256'][path]
    extra=['services/payment.py','services/order.py','services/inventory.py','services/checkout.py','services/background.py','tests/domain_contract.py']
    protected={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(set(manifest['protected_sha256'])|set(extra))}
    result={'benchmark_id':'sentinel-benchmark-v2','ground_truth_version':manifest['ground_truth_version'],
        'parent':'sentinel-benchmark-v1','created_at':datetime.now(timezone.utc).isoformat(),'protected_sha256':protected,
        'unchanged_from_v1':unchanged,'changes':[
            'Pure payment/order/inventory function extraction with added immutable contracts; candidate fixes remain unapplied.',
            'Notification consumer supervised reconnect and readiness, database pool readiness on startup.',
            'Checkout orchestration extracted from experiment wiring for safe source inspection; injection/scoring semantics unchanged.'],
        'comparison_limitations':'Final-release evaluation has changed business structure, readiness and readable source scope. Report separately from the six-version v1 comparison; no isolated compression or paired causal improvement claim.',
        'immutability':'Exclusive writes + SHA256 + read-only files; not administrator-proof WORM storage.'}
    folder=ROOT/'evaluation/benchmarks/sentinel-benchmark-v2';folder.mkdir(exist_ok=True)
    with (folder/'manifest.json').open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    with zipfile.ZipFile(folder/'business-source.zip','x',zipfile.ZIP_DEFLATED) as z:
        for name in protected: z.write(ROOT/name,name)
    for path in folder.iterdir(): path.chmod(0o444)
    print(json.dumps({'benchmark_id':result['benchmark_id'],'protected_files':len(protected),'unchanged_truth_scoring':True}))
if __name__=='__main__': main()
