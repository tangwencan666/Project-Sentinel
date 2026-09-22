"""Paired timing on an actual retained checkpoint; run only after formal suite ends."""
import asyncio
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
sys.path.insert(0,'/app')
from services.runtime import pool,query
from sentinel import security
from redaction import redact as candidate_redact

async def main():
    suite=json.loads(Path('/evidence/results/v3.1-first-controlled.json').read_text())
    assert suite['completed'],'Do not benchmark during the frozen formal suite'
    row=next(r for r in suite['results'] if r['scenario']=='n_plus_one')
    await pool.open()
    checkpoint=await query('SELECT payload FROM investigation_checkpoints WHERE run_id=%s',(row['run_id'],),one=True)
    await pool.close()
    data=checkpoint['payload'];original_settings=security.settings;counter=[0]
    def counted_settings():
        counter[0]+=1;return original_settings()
    security.settings=counted_settings
    timings=[]
    for iteration in range(3):
        counter[0]=0;started=time.perf_counter();old=security.redact(data)
        old_seconds=time.perf_counter()-started;old_reads=counter[0]
        counter[0]=0;started=time.perf_counter();new=candidate_redact(data,counted_settings)
        new_seconds=time.perf_counter()-started
        assert old==new,'Redaction security behavior changed'
        timings.append({'iteration':iteration+1,'original_seconds':old_seconds,'candidate_seconds':new_seconds,
                        'original_settings_reads':old_reads,'candidate_settings_reads':counter[0]})
    print(json.dumps({'scope':'Same retained real checkpoint, same frozen container image and mounted configuration; no model calls.',
        'incident_id':row['incident_id'],'checkpoint_chars':len(json.dumps(data)),
        'redacted_output_sha256':hashlib.sha256(json.dumps(new,sort_keys=True).encode()).hexdigest(),
        'equivalent_outputs':True,'timings':timings,
        'original_median_seconds':statistics.median(t['original_seconds'] for t in timings),
        'candidate_median_seconds':statistics.median(t['candidate_seconds'] for t in timings),
        'limits':'Three paired traversal timings; not end-to-end workflow latency or RCA accuracy.'}))

if __name__=='__main__': asyncio.run(main())
