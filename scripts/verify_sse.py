"""Verify new SSE events during an actual AI investigation, plus cursor replay."""
import json
import time
import urllib.request
from pathlib import Path
from evaluate_phase2 import api,BASE

deadline=time.monotonic()+100
while time.monotonic()<deadline:
    rows=api('/incidents')
    active=next((r for r in rows if r['mode']=='AI' and r['status'] in ('investigating','awaiting_recovery')),None)
    if active: break
    time.sleep(2)
else: raise RuntimeError('no active AI run during bounded SSE observation window')
iid=active['id'];incident=api('/incidents/'+iid)
cursor=max([s['id'] for s in incident['steps']]+[0]);events=[]
with urllib.request.urlopen(BASE+'/incidents/'+iid+'/events?after='+str(cursor),timeout=70) as response:
    assert response.headers.get_content_type()=='text/event-stream'
    for line in response:
        if time.monotonic()>deadline: break
        if line.startswith(b'data: '):
            row=json.loads(line[6:]);events.append({'id':row['id'],'kind':row['kind'],'agent':row['payload'].get('agent'),'ts':row['ts']})
            if len(events)>=3: break
assert events and all(e['id']>cursor for e in events)
request=urllib.request.Request(BASE+'/incidents/'+iid+'/events?after=0',headers={'Last-Event-ID':str(events[0]['id'])})
with urllib.request.urlopen(request,timeout=10) as response:
    for line in response:
        if line.startswith(b'data: '):
            replay=json.loads(line[6:]);assert replay['id']==events[1]['id'];break
out={'sse_verified':True,'mode':'AI','incident_id':iid,'starting_cursor':cursor,'new_events':events,'last_event_id_replay_verified':True}
Path('docs/sse-ai-verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=True))
