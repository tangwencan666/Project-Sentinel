"""Configurable, real three-process candidate environment with scoped dependencies."""
import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
import httpx
import psycopg
from psycopg.rows import dict_row
import redis.asyncio as redis_async
from aiokafka import AIOKafkaConsumer,TopicPartition
from aiokafka.admin import AIOKafkaAdminClient,NewTopic
from .generic_patching import ROOT,PROFILES
from .ai_patching import percentile

@dataclass(frozen=True)
class SandboxOptions:
    replay_requests:int=8
    redis_enabled:bool=True
    kafka_enabled:bool=True
    def __post_init__(self):
        if not 1<=self.replay_requests<=20: raise ValueError('Replay requests must be 1..20')

def port():
    with socket.socket() as sock: sock.bind(('127.0.0.1',0));return sock.getsockname()[1]

async def replay(component,path,candidate,options=None):
    options=options or SandboxOptions()
    if path not in PROFILES or PROFILES[path]['component']!=component: raise ValueError('Unknown candidate profile')
    token=uuid.uuid4().hex[:24];schema='candidate_'+token;topic='sentinel-candidate-'+token
    directory=candidate.parent/('http-'+token);directory.mkdir(parents=True)
    urls={role:'http://127.0.0.1:'+str(port()) for role in ('inventory','payment','order')}
    sources={p:str(candidate) if p==path else str(ROOT/p) for p in PROFILES}
    cache=redis_async.from_url(os.environ['REDIS_URL'],decode_responses=True)
    admin=None;processes=[];logs=[];topic_created=False;schema_created=False
    async with await psycopg.AsyncConnection.connect(os.environ['DATABASE_URL'],autocommit=True,row_factory=dict_row) as conn:
        async def sql(statement,params=(),one=False):
            cursor=await conn.execute(statement,params)
            if cursor.description: return await cursor.fetchone() if one else await cursor.fetchall()
        async def seed():
            await sql('TRUNCATE '+schema+'.products')
            await sql('INSERT INTO '+schema+'.products(id,name,price,stock) VALUES(1,%s,10,10)',('sandbox product',))
            await cache.delete(schema+':catalog')
        try:
            await sql('CREATE SCHEMA '+schema);schema_created=True
            await sql('CREATE TABLE '+schema+'.products(id integer PRIMARY KEY,name text,price numeric,stock integer)')
            await sql('CREATE TABLE '+schema+'.orders(id uuid PRIMARY KEY,total numeric)')
            await sql('CREATE TABLE '+schema+'.payments(order_id uuid PRIMARY KEY,amount numeric)')
            await seed()
            if options.kafka_enabled:
                admin=AIOKafkaAdminClient(bootstrap_servers=os.environ['KAFKA_BOOTSTRAP']);await admin.start()
                await admin.create_topics([NewTopic(topic,num_partitions=1,replication_factor=1)]);topic_created=True
            env={k:os.environ[k] for k in ('PATH','DATABASE_URL','REDIS_URL','KAFKA_BOOTSTRAP')}
            env.update(PYTHONPATH='/app',PYTHONDONTWRITEBYTECODE='1')
            for role in ('inventory','payment','order'):
                config={'role':role,'schema':schema,'topic':topic,'sources':sources,'urls':urls,
                    'port':int(urls[role].rsplit(':',1)[1]),'redis_enabled':options.redis_enabled,'kafka_enabled':options.kafka_enabled}
                cfg=directory/(role+'.json');cfg.write_text(json.dumps(config))
                logfile=(directory/(role+'.stderr')).open('w');logs.append(logfile)
                processes.append(subprocess.Popen([sys.executable,'-m','sentinel.sandbox_worker',str(cfg)],
                    cwd='/app',env=env,stdout=subprocess.DEVNULL,stderr=logfile))
            async with httpx.AsyncClient(timeout=5) as client:
                for _ in range(80):
                    if any(p.poll() is not None for p in processes):
                        failures={p.name:p.read_text() for p in directory.glob('*.stderr')}
                        raise RuntimeError('Candidate worker exited before readiness: '+json.dumps(failures))
                    try:
                        responses=await asyncio.gather(*(client.get(url+'/health') for url in urls.values()))
                        if all(r.status_code==200 for r in responses): break
                    except httpx.HTTPError: pass
                    await asyncio.sleep(.1)
                else: raise TimeoutError('Multi-service sandbox readiness timeout')
                if component=='order': await sql('TRUNCATE '+schema+'.products')
                if component=='inventory': await sql('UPDATE '+schema+'.products SET stock=-1')
                await cache.delete(schema+':catalog')
                observations=[];start=time.monotonic()
                for index in range(options.replay_requests):
                    begin=time.monotonic()
                    if component=='payment':
                        response=await client.post(urls['payment']+'/charge',json={'order_id':str(uuid.uuid4()),'amount':-2})
                        expected=422
                    elif component=='inventory':
                        response=await client.get(urls['inventory']+'/products');expected=503
                    else:
                        response=await client.post(urls['order']+'/checkout',json={'discount':None} if component=='pricing' else {})
                        expected=200 if component=='pricing' else 409
                    try: body=response.json()
                    except ValueError: body={'non_json_response':response.text}
                    observations.append({'status':response.status_code,'expected_status':expected,
                        'contract_satisfied':response.status_code==expected,'body':body,
                        'duration_ms':(time.monotonic()-begin)*1000})
                elapsed=time.monotonic()-start
                invalid_payments=await sql('SELECT count(*) AS n FROM '+schema+'.payments WHERE amount<0',one=True)
                await seed()
                healthy=await client.post(urls['order']+'/checkout',json={});healthy_body=healthy.json()
                counts={table:(await sql('SELECT count(*) AS n FROM '+schema+'.'+table,one=True))['n'] for table in ('orders','payments')}
                event_verified=None
                if options.kafka_enabled:
                    consumer=AIOKafkaConsumer(bootstrap_servers=os.environ['KAFKA_BOOTSTRAP'],group_id=None,enable_auto_commit=False)
                    await consumer.start()
                    try:
                        tp=TopicPartition(topic,0);consumer.assign([tp]);consumer.seek(tp,0)
                        batches=await consumer.getmany(timeout_ms=2500,max_records=50)
                        event_verified=any(json.loads(m.value).get('order_id')==healthy_body.get('order_id') for batch in batches.values() for m in batch)
                    finally: await consumer.stop()
                durations=[o['duration_ms'] for o in observations]
                result={'source':'Measured','profile':component,'requests':len(observations),'observations':observations,
                    'business_violation_pct':100*sum(not o['contract_satisfied'] for o in observations)/len(observations),
                    'error_pct':100*sum(o['status']>=500 for o in observations)/len(observations),
                    'p50_ms':percentile(durations,.5),'p95_ms':percentile(durations,.95),'p99_ms':percentile(durations,.99),
                    'throughput_rps':len(observations)/elapsed,'duration_seconds':elapsed,
                    'healthy_control_passed':healthy.status_code==200 and healthy_body.get('total')==10 and counts['orders']>0 and counts['payments']>0 and (event_verified if options.kafka_enabled else True),
                    'dependencies':{'postgres':{'schema':schema,'rows':counts,'invalid_payments':invalid_payments['n']},
                        'redis':{'enabled':options.redis_enabled,'namespace':schema,'catalog_ttl':await cache.ttl(schema+':catalog')},
                        'kafka':{'enabled':options.kafka_enabled,'topic':topic,'healthy_order_event_verified':event_verified}},
                    'services':list(urls),'isolation':'Dedicated PostgreSQL schema, Redis namespace and Kafka topic; bounded non-root processes share Sentinel container/kernel',
                    'interpretation':'Rejected invalid data may increase 4xx/503. Compare business contract violations separately from HTTP error rates.',
                    'automatic_apply_allowed':False}
                (directory/'observations.json').write_text(json.dumps(result,indent=2))
                return result
        finally:
            for process in processes:
                if process.poll() is None: process.terminate()
            for process in processes:
                try: await asyncio.to_thread(process.wait,3)
                except subprocess.TimeoutExpired: process.kill();await asyncio.to_thread(process.wait)
            for logfile in logs: logfile.close()
            await cache.delete(schema+':catalog');await cache.aclose()
            if admin:
                try:
                    if topic_created: await admin.delete_topics([topic])
                finally: await admin.close()
            if schema_created: await sql('DROP SCHEMA '+schema+' CASCADE')
