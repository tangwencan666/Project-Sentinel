"""Investigator capability boundary. No fault registry, Redis enumeration, shell, or arbitrary file reads."""
import json
import os
import time
from pathlib import Path
import httpx
import psycopg
from psycopg.rows import dict_row
from aiokafka import AIOKafkaConsumer
from .patching import propose
from services.runtime import redis

READ_DSN='postgresql://investigator:local-investigator@postgres:5432/sentinel'
SERVICES=['gateway','user-service','order-service','payment-service','inventory-service','notification-service']

async def sql(statement,args=()):
    async with await psycopg.AsyncConnection.connect(READ_DSN,row_factory=dict_row,autocommit=True) as conn:
        await conn.execute("SET statement_timeout='3s'")
        cur=await conn.execute(statement,args or None)
        return await cur.fetchall()

async def logs(service=None):
    return await sql("SELECT * FROM request_logs WHERE ts>now()-interval '5 minutes' AND (%s::text IS NULL OR service=%s) ORDER BY id DESC LIMIT 60",(service,service))

async def summary(seconds=30):
    return await sql("SELECT service,count(*) requests,count(*)/%s::float throughput_rps,round((avg((status>=500)::int)*100)::numeric,2) error_pct,round(avg(duration_ms)::numeric,2) avg_ms,percentile_cont(0.5) WITHIN GROUP(ORDER BY duration_ms) p50_ms,percentile_cont(0.95) WITHIN GROUP(ORDER BY duration_ms) p95_ms,percentile_cont(0.99) WITHIN GROUP(ORDER BY duration_ms) p99_ms FROM request_logs WHERE ts>now()-(%s * interval '1 second') GROUP BY service ORDER BY service",(seconds,seconds))

async def metrics():
    queries={'requests':'sum by(service) (rate(commerce_requests_total[1m]))','errors':'sum by(service) (rate(commerce_requests_total{status=~"5.."}[1m]))','p95':'histogram_quantile(0.95, sum by(le,service)(rate(commerce_request_seconds_bucket[1m])))','db_qps':'sum by(service)(rate(commerce_db_queries_total[1m]))'}
    async with httpx.AsyncClient(timeout=8) as client:
        result={}
        for name,q in queries.items():
            response=await client.get('http://prometheus:9090/api/v1/query',params={'query':q})
            response.raise_for_status(); result[name]=response.json()
        return result

async def database():
    # Diagnostic SQL contains business query literals. Exclude the observer itself.
    return {'activity':await sql("SELECT application_name,state,wait_event_type,wait_event,query FROM pg_stat_activity WHERE datname=current_database() AND application_name != '' LIMIT 30"),'statements':await sql("SELECT userid,dbid,queryid,query,calls,mean_exec_time,rows FROM pg_stat_statements WHERE (query LIKE 'SELECT%FROM products%' OR query LIKE 'SELECT pg_sleep%') AND query NOT ILIKE '%pg_stat_%' ORDER BY query,queryid")}

async def cache():
    info=await redis.info('stats')
    return {'catalog_ttl':await redis.ttl('catalog'),'keyspace_hits':info['keyspace_hits'],'keyspace_misses':info['keyspace_misses'],'note':'Redis stats are cumulative and include control-plane requests; compare snapshots.'}

async def kafka():
    consumer=AIOKafkaConsumer(bootstrap_servers=os.environ['KAFKA_BOOTSTRAP'],group_id='notifications',enable_auto_commit=False)
    await consumer.start()
    try:
        from aiokafka import TopicPartition
        partitions=consumer.partitions_for_topic('orders')
        tps=[TopicPartition('orders',n) for n in (partitions or [])]
        ends=await consumer.end_offsets(tps)
        result=[]
        for tp,end in ends.items():
            committed=await consumer.committed(tp)
            result.append({'partition':tp.partition,'end_offset':end,'committed_offset':committed,'lag':end-(committed or 0)})
        return result
    finally: await consumer.stop()

async def traces(trace_id=None):
    async with httpx.AsyncClient(timeout=8) as client:
        if trace_id:
            if len(trace_id)!=32 or any(c not in '0123456789abcdef' for c in trace_id): raise ValueError('invalid trace ID')
            response=await client.get('http://jaeger:16686/api/traces/'+trace_id)
        else:
            # Exclude the newest batch-export interval; otherwise results are often incomplete traces.
            end=int((time.time()-12)*1_000_000)
            response=await client.get('http://jaeger:16686/api/traces',params={'service':'gateway','operation':'POST /checkout','limit':3,'start':end-300_000_000,'end':end})
        response.raise_for_status()
        body=response.json()
        return [{'traceID':t['traceID'],'processes':t['processes'],'spans':[{'operation':s['operationName'],'processID':s['processID'],'duration_us':s['duration'],'spanID':s['spanID'],'startTime':s['startTime'],'references':s.get('references',[]),'tags':s.get('tags',[])} for s in t['spans']]} for t in body.get('data',[])]

SPECS=[
 ('query_logs','Read recent structured HTTP logs.',{'service':{'type':'string','enum':SERVICES}}),
 ('query_metrics','Read current Prometheus rates and p95.',{}),
 ('query_traces','Read real distributed traces; optionally use trace_id from logs.',{'trace_id':{'type':'string'}}),
 ('inspect_database','Inspect active queries and pg_stat_statements.',{}),
 ('inspect_cache','Read catalog TTL and Redis counters.',{}),
 ('inspect_queue','Read actual Kafka end and committed offsets.',{}),
 ('read_code','Read allowlisted pricing source. Other source files are not exposed in this version.',{}),
 ('propose_patch','Submit complete replacement pricing.py source. Runs immutable regression tests against baseline and candidate; does not deploy.',{'source':{'type':'string'}}),
]
TOOLS=[{'type':'function','function':{'name':name,'description':desc,'parameters':{'type':'object','properties':props,'required':['source'] if name=='propose_patch' else [],'additionalProperties':False}}} for name,desc,props in SPECS]

async def execute(name,args,incident_id):
    if name=='query_logs': return await logs(args.get('service'))
    if name=='query_metrics': return await metrics()
    if name=='query_traces': return await traces(args.get('trace_id'))
    if name=='inspect_database': return await database()
    if name=='inspect_cache': return await cache()
    if name=='inspect_queue': return await kafka()
    if name=='read_code': return {'path':'services/pricing.py','source':Path('/app/services/pricing.py').read_text()}
    if name=='propose_patch':
        import asyncio
        return await asyncio.to_thread(propose,args['source'],incident_id)
    raise ValueError('tool not allowlisted')
