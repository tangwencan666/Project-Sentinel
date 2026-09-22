"""Apply the declared post-evaluation operational retry without changing nominal faults."""
import hashlib
import json
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from post_eval_changes import worker_recovery_only

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'services/app.py'
before=path.read_bytes()
with zipfile.ZipFile(ROOT/'evaluation/frozen-framework.zip') as archive:
    assert before==archive.read('services/app.py')
text=before.decode()
newline='\r\n' if '\r\n' in text else '\n'
text=text.replace('import httpx'+newline,'import httpx'+newline+'from redis.exceptions import RedisError'+newline,1)
start=text.index('    while True:',text.index('async def exhaust():'))
end=text.index(newline+'@asynccontextmanager',start)
body=text[start:end]
lines=body.splitlines()
while lines and not lines[-1]:lines.pop()
replacement=lines[0]+newline+'        try:'+newline+newline.join('    '+line for line in lines[1:])+newline+'        except RedisError:'+newline+'            await asyncio.sleep(1)'+newline
text=text[:start]+replacement+text[end:]
after=text.encode()
assert worker_recovery_only(before,after)
path.write_bytes(after)
record={'at':datetime.now(timezone.utc).isoformat(),'path':'services/app.py',
    'cause':'A transient Redis DNS connection failure escaped the background exhaust task; later healthy HTTP did not restart it.',
    'scope':'Only catch RedisError and retry after one second in the fault worker. Existing triggers, hold duration, concurrency, SQL and business handlers are unchanged; cancellation still propagates.',
    'applied_after_frozen_evaluation':True,'ast_only_declared_change':True,
    'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest(),
    'evidence':'evaluation/pool-fixture-proof.json','frozen_source':'evaluation/frozen-framework.zip'}
with (ROOT/'evaluation/fault-worker-recovery-fix.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
print(json.dumps(record))
