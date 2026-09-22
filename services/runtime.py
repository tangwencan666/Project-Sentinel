import os
import json
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import Response
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from redis.asyncio import Redis
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

SERVICE = os.getenv('SERVICE_NAME', 'sentinel')
DSN = os.environ['DATABASE_URL']
pool = AsyncConnectionPool(DSN, min_size=1, max_size=4, timeout=0.8, open=False, kwargs={'autocommit': True, 'row_factory': dict_row, 'application_name': SERVICE})
audit_pool = AsyncConnectionPool(DSN, min_size=1, max_size=2, open=False, kwargs={'autocommit': True})
redis = Redis.from_url(os.environ['REDIS_URL'], decode_responses=True)
requests = Counter('commerce_requests_total', 'Completed HTTP requests', ['service','path','status'])
latency = Histogram('commerce_request_seconds', 'HTTP wall time', ['service','path'], buckets=(.01,.05,.1,.25,.5,1,2,5,10,30))
db_queries = Counter('commerce_db_queries_total', 'Business database statements', ['service'])
log = logging.getLogger(SERVICE)
logging.basicConfig(level=logging.INFO)

async def query(sql, args=(), one=False):
    db_queries.labels(SERVICE).inc()
    async with pool.connection() as conn:
        cur = await conn.execute(sql, args)
        if cur.description:
            return await cur.fetchone() if one else await cur.fetchall()

async def fault(name):
    return bool(await redis.exists('fault:' + name))

def instrument(app):
    provider = TracerProvider(resource=Resource.create({'service.name': SERVICE}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=os.environ['OTEL_EXPORTER_OTLP_ENDPOINT']+'/v1/traces')))
    trace.set_tracer_provider(provider)
    HTTPXClientInstrumentor().instrument()
    PsycopgInstrumentor().instrument()
    RedisInstrumentor().instrument()
    FastAPIInstrumentor.instrument_app(app, excluded_urls='health,metrics')

    @app.middleware('http')
    async def record(request: Request, call_next):
        if request.url.path in ('/health','/metrics'):
            return await call_next(request)
        start = time.perf_counter()
        status, error = 500, None
        tid = format(trace.get_current_span().get_span_context().trace_id, '032x')
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers['X-Trace-ID'] = tid
            return response
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            log.exception('request failed')
            from fastapi.responses import JSONResponse
            return JSONResponse({'error': error, 'trace_id': tid}, status_code=500)
        finally:
            duration = time.perf_counter()-start
            path = request.scope.get('route')
            path = getattr(path, 'path', request.url.path)
            requests.labels(SERVICE,path,str(status)).inc()
            latency.labels(SERVICE,path).observe(duration)
            event = dict(service=SERVICE,path=path,status=status,duration_ms=round(duration*1000,2),trace_id=tid,error=error)
            log.info(json.dumps(event))
            try:
                async with audit_pool.connection() as conn:
                    await conn.execute('INSERT INTO request_logs(service,path,status,duration_ms,trace_id,error) VALUES(%s,%s,%s,%s,%s,%s)', tuple(event.values()))
            except Exception:
                log.exception('audit persistence failed')

    @app.get('/metrics')
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get('/health')
    async def health():
        await query('SELECT 1')
        await redis.ping()
        worker=getattr(app.state,'background_health',None)
        task=getattr(app.state,'consumer_task',None)
        if worker is not None and (not worker.get('ready') or task is None or task.done()):
            from fastapi.responses import JSONResponse
            return JSONResponse({'service':SERVICE,'status':'unhealthy','background':worker},status_code=503)
        return {'service':SERVICE,'status':'healthy','background':worker}

    @app.get('/pool-stats')
    async def pool_stats():
        return {'service':SERVICE,'source':'Measured','pool':pool.get_stats()}
