import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
import httpx
from redis.exceptions import RedisError
from fastapi import FastAPI, HTTPException
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from opentelemetry import trace, propagate
from .runtime import SERVICE, pool, audit_pool, redis, query, fault, instrument
from .pricing import total
from .payment import normalize_amount
from .inventory import normalize_product
from .checkout import checkout as checkout_order
from .background import supervise

producer = None
client = None
tracer = trace.get_tracer(__name__)

async def consume_messages(consumer):
    async for message in consumer:
        while await fault('consumer_lag'):
            await asyncio.sleep(1)
        event = json.loads(message.value)
        context = propagate.extract(event.get('trace', {}))
        with tracer.start_as_current_span('orders consume', context=context):
            await query('INSERT INTO notifications(order_id) VALUES(%s) ON CONFLICT DO NOTHING', (event['order_id'],))
            await consumer.commit()
            await redis.set('notification:last_offset', message.offset)

async def consume(status):
    def factory():
        return AIOKafkaConsumer('orders', bootstrap_servers=os.environ['KAFKA_BOOTSTRAP'], group_id='notifications', auto_offset_reset='earliest', enable_auto_commit=False)
    await supervise(factory,consume_messages,status)

async def exhaust():
    async def hold():
        async with pool.connection() as conn:
            await conn.execute('SELECT pg_sleep(2)')
    while True:
        try:
            if SERVICE == 'inventory-service' and await fault('pool_exhaustion'):
                await asyncio.gather(*(hold() for _ in range(4)), return_exceptions=True)
            else:
                await asyncio.sleep(.2)
        except RedisError:
            await asyncio.sleep(1)

@asynccontextmanager
async def lifespan(app):
    global producer, client
    await pool.open(); await audit_pool.open()
    await pool.wait(timeout=30); await audit_pool.wait(timeout=30)
    client = httpx.AsyncClient(timeout=2)
    tasks = [asyncio.create_task(exhaust())]
    if SERVICE == 'order-service':
        producer = AIOKafkaProducer(bootstrap_servers=os.environ['KAFKA_BOOTSTRAP'])
        await producer.start()
    if SERVICE == 'notification-service':
        app.state.background_health={'ready':False,'restarts':0,'last_error':None}
        task=asyncio.create_task(consume(app.state.background_health))
        app.state.consumer_task=task
        tasks.append(task)
    yield
    for task in tasks:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    if producer: await producer.stop()
    await client.aclose(); await redis.aclose(); await pool.close(); await audit_pool.close()

app = FastAPI(title=SERVICE, lifespan=lifespan)
instrument(app)

async def downstream(service, path, payload=None):
    attempts = 5 if await fault('retry_storm') and service == 'payment-service' else 1
    for attempt in range(attempts):
        try:
            response = await client.request('POST' if payload is not None else 'GET', f'http://{service}:8000{path}', json=payload)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError,) as exc:
            if attempt == attempts-1:
                raise HTTPException(502, f'{service}: {type(exc).__name__}') from exc

@app.get('/user')
async def user():
    if SERVICE != 'user-service': raise HTTPException(404)
    return await query('SELECT * FROM users WHERE id=1', one=True)

@app.get('/products')
async def products():
    if SERVICE == 'gateway': return await downstream('inventory-service','/products')
    if SERVICE != 'inventory-service': raise HTTPException(404)
    slow, nplus, miss = await fault('slow_query'), await fault('n_plus_one'), await fault('cache_miss')
    cached = await redis.get('catalog')
    if cached and not (slow or nplus or miss or await fault('pool_exhaustion')):
        return json.loads(cached)
    if slow: await query('SELECT pg_sleep(1.2)')
    if nplus:
        ids = await query('SELECT id FROM products ORDER BY id LIMIT 40')
        rows = [await query('SELECT id,name,price,stock FROM products WHERE id=%s',(item['id'],), one=True) for item in ids]
    else:
        rows = await query('SELECT id,name,price,stock FROM products ORDER BY id LIMIT 40')
    try: rows = [normalize_product(row) for row in rows]
    except ValueError as exc: raise HTTPException(503, 'invalid catalog record') from exc
    if not miss: await redis.set('catalog',json.dumps(rows),ex=30)
    else: await redis.delete('catalog')
    return rows

@app.post('/checkout')
async def checkout():
    if SERVICE == 'gateway':
        await downstream('user-service','/user')
        return await downstream('order-service','/checkout',{})
    if SERVICE != 'order-service': raise HTTPException(404)
    items = await downstream('inventory-service','/products')
    pricing = total
    patch = await redis.get('repair:pricing')
    if patch:
        from sentinel.patching import validate
        validate(patch)
        namespace = {'__builtins__': {'round':round,'ValueError':ValueError,'float':float,'int':int}}
        exec(compile(patch,'validated_pricing.py','exec'),namespace)
        pricing = namespace['total']
    return await checkout_order(items,None if await fault('code_exception') else 0,pricing,downstream,query,producer)

@app.post('/charge')
async def charge(payload: dict):
    if SERVICE != 'payment-service': raise HTTPException(404)
    if await fault('downstream_timeout'): await asyncio.sleep(3)
    if await fault('retry_storm'): raise HTTPException(503,'payment processor unavailable')
    try: amount = normalize_amount(payload['amount'])
    except ValueError as exc: raise HTTPException(422, 'invalid amount') from exc
    await query('INSERT INTO payments(order_id,amount) VALUES(%s,%s) ON CONFLICT DO NOTHING',(payload['order_id'],amount))
    return {'status':'charged'}
