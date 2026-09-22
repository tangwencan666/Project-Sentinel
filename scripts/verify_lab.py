"""Real integration acceptance. Requires a running Compose stack. No LLM or mocked data.
Run: python scripts/verify_lab.py --output docs/verification.json
"""
import argparse
import concurrent.futures
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API='http://127.0.0.1:18082/api'
GATEWAY='http://127.0.0.1:18081'
results=[]

def request(path,method='GET',body=None,gateway=False):
    req=urllib.request.Request((GATEWAY if gateway else API)+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    start=time.monotonic()
    try:
        response=urllib.request.urlopen(req,timeout=20)
    except urllib.error.HTTPError as exc:
        response=exc
    content=response.read()
    return response.code,json.loads(content) if content else None,time.monotonic()-start

def api(path,method='GET',body=None):
    status,data,_=request(path,method,body)
    assert status==200,(path,status,data)
    return data

def trigger(name): api('/faults/'+name,'POST',{'duration_seconds':90})
def stop(name): api('/faults/'+name,'DELETE');time.sleep(2.2)
def sample(): return request('/products',gateway=True)
def checkout(): return request('/checkout','POST',{},gateway=True)
def record(name,observed):
    results.append({'scenario':name,'passed':True,'observed':observed})
    print(json.dumps(results[-1],ensure_ascii=False),flush=True)

def product_calls():
    data=api('/evidence/database')
    return sum(s['calls'] for s in data['statements'] if 'FROM products' in s['query'])

def run():
    api('/traffic/false','POST');api('/recover','POST');api('/rollback','POST');time.sleep(4)
    status,data,duration=checkout();assert status==200,(status,data)
    record('healthy_checkout',{'order_id':data['order_id'],'seconds':duration})
    trigger('slow_query')
    status,_,duration=sample();assert status==200 and duration>=1.1,(status,duration)
    record('slow_query',{'status':status,'seconds':duration});stop('slow_query')
    trigger('pool_exhaustion');time.sleep(.4)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        samples=list(executor.map(lambda _:sample(),range(8)))
    failures=[s for s in samples if s[0]>=500]
    assert failures,samples
    record('pool_exhaustion',{'statuses':[s[0] for s in samples]});stop('pool_exhaustion')
    before=product_calls();trigger('n_plus_one');status,_,_=sample();after=product_calls()
    assert status==200 and after-before>=41,(status,before,after)
    record('n_plus_one',{'sql_calls_delta':after-before});stop('n_plus_one')
    sample();before=product_calls();sample();warm=product_calls()-before
    trigger('cache_miss');before=product_calls()
    for _ in range(5): assert sample()[0]==200
    cold=product_calls()-before;cache=api('/evidence/cache')
    assert warm==0 and cold>=5 and cache['catalog_ttl']==-2,(warm,cold,cache)
    record('cache_miss',{'warm_sql':warm,'cold_sql':cold,'catalog_ttl':cache['catalog_ttl']});stop('cache_miss')
    trigger('consumer_lag')
    for _ in range(12): assert checkout()[0]==200
    time.sleep(2);queue=api('/evidence/queue')
    assert sum(p['lag'] for p in queue)>=12,queue
    record('consumer_lag',{'offsets':queue});stop('consumer_lag')
    for _ in range(10):
        if sum(p['lag'] for p in api('/evidence/queue'))==0: break
        time.sleep(1)
    assert sum(p['lag'] for p in api('/evidence/queue'))==0
    trigger('downstream_timeout');status,data,duration=checkout()
    assert status==502 and duration>=1.8,(status,data,duration)
    record('downstream_timeout',{'status':status,'seconds':duration});stop('downstream_timeout')
    before=max([r['id'] for r in api('/evidence/logs')]+[0]);trigger('retry_storm');status,_,_=checkout()
    logs=api('/evidence/logs');amplified=[r for r in logs if r['id']>before and r['service']=='payment-service' and r['status']==503]
    assert status==502 and len(amplified)==5,(status,amplified)
    record('retry_storm',{'payment_503_calls_per_checkout':len(amplified)});stop('retry_storm')
    trigger('code_exception');status,_,_=checkout()
    errors=[r for r in api('/evidence/logs') if r['service']=='order-service' and 'NoneType' in (r['error'] or '')]
    assert status==502 and errors,(status,errors)
    record('code_exception',{'error':errors[0]['error'],'trace_id':errors[0]['trace_id']})
    api('/traffic/true','POST')
    for _ in range(8):
        incidents=api('/incidents')
        if any(i['signal'].get('source')!='operator_requested' and i['signal'].get('signals') for i in incidents): break
        time.sleep(5)
    assert incidents,'detector created no incident'
    record('incident_detection',{'id':incidents[0]['id'],'status':incidents[0]['status']})
    stop('code_exception');time.sleep(6)
    trace_data=api('/evidence/traces')
    assert trace_data and any(len(t['processes'])>=3 for t in trace_data),trace_data
    record('distributed_traces',{'traces':len(trace_data),'max_services':max(len(t['processes']) for t in trace_data)})
    metrics=api('/evidence/metrics')
    assert metrics['requests']['data']['result']
    record('prometheus',{'series':len(metrics['requests']['data']['result'])})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='docs/verification.json');args=parser.parse_args()
    error=None
    try:run()
    except Exception as exc:
        error=repr(exc);raise
    finally:
        api('/recover','POST');api('/traffic/true','POST')
        Path(args.output).write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'results':results,'error':error,'llm_verified':False},ensure_ascii=False,indent=2),encoding='utf-8')
