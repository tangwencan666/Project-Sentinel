"""V4 timed read-only infrastructure probes; scope and unknowns are explicit."""
import asyncio
from datetime import datetime,timezone
import time
from . import evidence as adapters
from .tool_registry import statement_deltas

def now(): return datetime.now(timezone.utc).isoformat()
def rate(before,after,seconds):
    return (after-before)/seconds if before is not None and after is not None and after>=before and seconds>0 else None

async def redis_observation():
    first=await adapters.redis.info();start=time.monotonic();at=now()
    await asyncio.sleep(1)
    last=await adapters.redis.info();seconds=time.monotonic()-start
    ping=time.monotonic();await adapters.redis.ping();latency=(time.monotonic()-ping)*1000
    hits=rate(first.get('keyspace_hits'),last.get('keyspace_hits'),seconds)
    misses=rate(first.get('keyspace_misses'),last.get('keyspace_misses'),seconds)
    return {'catalog_ttl':await adapters.redis.ttl('catalog'),'keyspace_hits':last.get('keyspace_hits'),
        'keyspace_misses':last.get('keyspace_misses'),'hit_rate':hits,'miss_rate':misses,
        'rate_unit':'operations/second','hit_ratio':hits/(hits+misses) if hits is not None and misses is not None and hits+misses>0 else None,
        'evictions':last.get('evicted_keys'),'eviction_rate':rate(first.get('evicted_keys'),last.get('evicted_keys'),seconds),
        'memory_bytes':last.get('used_memory'),'latency_ms':latency,'errors':last.get('total_error_replies'),
        'window':{'start':at,'end':now(),'seconds':seconds},
        'scope':'global Redis counters include control-plane requests; NOT catalog-only hit ratio. Errors/evictions cumulative.'}

async def kafka_observation():
    before=await adapters.kafka();start=time.monotonic();at=now();await asyncio.sleep(1)
    after=await adapters.kafka();seconds=time.monotonic()-start;old={r['partition']:r for r in before}
    return [{**row,'consumer_group':'notifications','topic':'orders',
        'producer_rate':rate(old.get(row['partition'],{}).get('end_offset'),row['end_offset'],seconds),
        'consumer_rate':rate(old.get(row['partition'],{}).get('committed_offset'),row['committed_offset'],seconds),
        'rate_unit':'messages/second','window':{'start':at,'end':now(),'seconds':seconds}}
        for row in after]

async def postgres_observation():
    before=await adapters.database();start=time.monotonic();at=now();await asyncio.sleep(1)
    after=await adapters.database()
    after.update(call_deltas=statement_deltas(before['statements'],after['statements']),
                 sample_seconds=time.monotonic()-start,window={'start':at,'end':now()},source='Measured')
    after['locks']=await adapters.sql("SELECT a.application_name,l.locktype,l.mode,l.granted,count(*) AS count FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid WHERE a.datname=current_database() AND a.application_name!='' GROUP BY a.application_name,l.locktype,l.mode,l.granted ORDER BY a.application_name LIMIT 40")
    after['slow_queries']=await adapters.sql("SELECT application_name,state,wait_event,query,extract(epoch FROM clock_timestamp()-query_start) AS elapsed_seconds FROM pg_stat_activity WHERE datname=current_database() AND application_name!='' AND state='active' AND query_start<clock_timestamp()-interval '100 milliseconds' LIMIT 20")
    return after
