"""Select the measured, more reliable default after retaining the exact benchmark code."""
import hashlib
import json
from pathlib import Path
import zipfile
from datetime import datetime,timezone
from phase3_dataset import dataset_path

ROOT=Path(__file__).resolve().parents[1]


def main():
    suites=[json.loads(dataset_path(v).read_text(encoding='utf-8')) for v in ('v2','v3')]
    assert all(s['completed'] and s.get('selection_policy') for s in suites)
    assert sum(r.get('workflow_completed',False) for r in suites[0]['results'])>sum(r.get('workflow_completed',False) for r in suites[1]['results'])
    hashes=suites[0]['source_sha256'];assert hashes==suites[1]['source_sha256']
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in hashes.items())
    frozen=ROOT/'evaluation/frozen-framework.zip'
    with zipfile.ZipFile(frozen,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for p in hashes:archive.write(ROOT/p,p)
    path=ROOT/'sentinel/api.py';before=path.read_bytes()
    assert before.count(b"='HYBRID_V3'")==3
    after=before.replace(b"='HYBRID_V3'",b"='HYBRID_V2'")
    path.write_bytes(after)
    record={'at':datetime.now(timezone.utc).isoformat(),'scope':'Only default mode selection after evaluation; explicitly selected V3 still runs V3, no silent fallback.',
            'path':'sentinel/api.py','replacements':3,'before_sha256':hashlib.sha256(before).hexdigest(),
            'after_sha256':hashlib.sha256(after).hexdigest(),'old_default':'HYBRID_V3','new_default':'HYBRID_V2',
            'frozen_framework':'evaluation/frozen-framework.zip','frozen_framework_sha256':hashlib.sha256(frozen.read_bytes()).hexdigest()}
    with (ROOT/'evaluation/post-evaluation-default.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
    print(json.dumps(record))


if __name__=='__main__':main()
