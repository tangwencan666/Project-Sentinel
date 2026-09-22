"""Unified diff validation and isolated integration replay, extending phase-one runner."""
import asyncio
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import uuid
import httpx
from .patching import BASE,validate,propose,limits

def apply_diff(base,diff):
    if len(diff)>16000: raise ValueError('diff exceeds size limit')
    # JSON transports commonly omit the final newline of the diff envelope.
    # Source EOF semantics still require an explicit marker (rejected below).
    if not diff.endswith('\n'): diff+='\n'
    lines=diff.splitlines(keepends=True)
    if lines and lines[0].startswith('diff --git '):
        if lines[0].strip()!='diff --git a/services/pricing.py b/services/pricing.py': raise ValueError('path not allowed')
        lines=lines[1:]
        if lines and lines[0].startswith('index '): lines=lines[1:]
    if len(lines)<3 or lines[0].strip()!='--- a/services/pricing.py' or lines[1].strip()!='+++ b/services/pricing.py': raise ValueError('only services/pricing.py may be patched')
    original=base.splitlines(keepends=True);out=[];cursor=0;i=2
    while i<len(lines):
        match=re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n?',lines[i])
        if not match: raise ValueError('invalid unified diff hunk')
        old_start,old_count,new_start,new_count=match.groups();start=int(old_start)-1
        if start<cursor or start>len(original): raise ValueError('overlapping or out of range hunk')
        out+=original[cursor:start];cursor=start;i+=1;old_seen=new_seen=0
        if int(new_start)!=len(out)+1: raise ValueError('new hunk position mismatch')
        while i<len(lines) and not lines[i].startswith('@@ '):
            line=lines[i];i+=1
            if line.startswith('\\ No newline'): raise ValueError('source must use newline-terminated lines')
            if not line or line[0] not in (' ','+','-'): raise ValueError('invalid diff line')
            marker,content=line[0],line[1:]
            if marker in (' ','-'):
                if cursor>=len(original) or original[cursor]!=content: raise ValueError('patch context does not match base')
                cursor+=1;old_seen+=1
            if marker in (' ','+'): out.append(content);new_seen+=1
        if old_seen!=int(old_count or 1) or new_seen!=int(new_count or 1): raise ValueError('hunk length mismatch')
    out+=original[cursor:];source=''.join(out)
    if source==base: raise ValueError('empty patch')
    validate(source)
    return source

def percentile(values,q):
    ordered=sorted(values);index=(len(ordered)-1)*q;low=int(index);high=min(low+1,len(ordered)-1)
    return ordered[low]+(ordered[high]-ordered[low])*(index-low)

async def replay_source(path):
    with socket.socket() as sock: sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','sentinel.sandbox_server:app','--host','127.0.0.1','--port',str(port),'--log-level','critical'],cwd='/app',env={'PATH':os.environ['PATH'],'PYTHONPATH':'/app','PRICING_SOURCE':str(path),'PYTHONDONTWRITEBYTECODE':'1'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,preexec_fn=limits if os.name=='posix' else None)
    url=f'http://127.0.0.1:{port}'
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            for _ in range(50):
                if proc.poll() is not None: raise ValueError('sandbox process failed to start')
                try:
                    if (await client.get(url+'/health')).status_code==200: break
                except httpx.HTTPError: pass
                await asyncio.sleep(.1)
            else: raise ValueError('sandbox startup timeout')
            observations=[];started=time.perf_counter()
            for _ in range(20):
                begin=time.perf_counter();response=await client.post(url+'/checkout',json={'discount':None})
                observations.append({'status':response.status_code,'duration_ms':(time.perf_counter()-begin)*1000,'body':response.json()})
            elapsed=time.perf_counter()-started;durations=[x['duration_ms'] for x in observations]
            healthy=await client.post(url+'/checkout',json={'discount':0})
            healthy_body=healthy.json()
            return {'source':'Measured','scope':'isolated pricing HTTP replay with live inventory; no payment/order writes','requests':len(observations),'error_pct':100*sum(x['status']>=500 for x in observations)/len(observations),'p50_ms':percentile(durations,.5),'p95_ms':percentile(durations,.95),'p99_ms':percentile(durations,.99),'throughput_rps':len(observations)/elapsed,'duration_seconds':elapsed,'db_pool':None,'kafka_lag':None,'not_applicable':['db_pool','kafka_lag'],'healthy_control_passed':healthy.status_code==200 and healthy_body.get('total')==healthy_body.get('inventory_price'),'observations':observations}
    finally:
        proc.terminate()
        try: await asyncio.to_thread(proc.wait,3)
        except subprocess.TimeoutExpired: proc.kill();await asyncio.to_thread(proc.wait)

async def validate_ai_diff(diff,incident_id):
    source=apply_diff(BASE.read_text(),diff)
    result=await asyncio.to_thread(propose,source,incident_id)
    result['origin']='AI_GENERATED'
    result['submitted_diff']=diff
    result['sandbox_scope']='pricing function + live inventory, not full six-service isolated clone'
    result['candidate_verified']=False
    if not result['validated']:
        result['status']='TESTS_FAILED';return result
    directory=Path('/work')/str(incident_id)/result['sha256']
    before=await replay_source(directory/'baseline'/'pricing.py')
    after=await replay_source(directory/'candidate'/'pricing.py')
    passed=before['error_pct']==100 and after['error_pct']==0 and after['healthy_control_passed']
    result.update(replay={'before':before,'after':after,'passed':passed},candidate_verified=passed,status='CANDIDATE_VERIFIED' if passed else 'REPLAY_FAILED')
    return result
