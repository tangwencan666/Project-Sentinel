"""Trusted HTTP/I/O shell around AST-restricted candidate business functions."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import re
import sys
import uuid
import httpx
import psycopg
from psycopg.rows import dict_row
import redis.asyncio as redis_async
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI,HTTPException
from .generic_patching import ROOT,PROFILES,validate_source

def create_app(config):
    schema=config['schema']
    if not re.fullmatch(r'candidate_[0-9a-f]{24}',schema): raise ValueError('Invalid sandbox namespace')
    functions={}
    builtins={'round':round,'float':float,'int':int,'str':str,'len':len,'isinstance':isinstance,
              'ValueError':ValueError,'bool':bool,'dict':dict,'list':list}
    for path,profile in PROFILES.items():
        source=Path(config['sources'][path]).read_text();validate_source(path,source)
        namespace={'__builtins__':builtins}
        exec(compile(source,path,'exec'),namespace)
        functions[profile['component']]=namespace[profile['symbol']]
    cache=redis_async.from_url(os.environ['REDIS_URL'],decode_responses=True)
    producer=None
    async def query(statement,params=(),one=False):
        async with await psycopg.AsyncConnection.connect(os.environ['DATABASE_URL'],autocommit=True,row_factory=dict_row,
                application_name='candidate-'+config['role'],options='-c statement_timeout=3000') as conn:
            await conn.execute('SET search_path TO '+schema)
            cursor=await conn.execute(statement,params)
            if cursor.description: return await cursor.fetchone() if one else await cursor.fetchall()
    @asynccontextmanager
    async def lifespan(app):
        nonlocal producer
        if config['role']=='order' and config['kafka_enabled']:
            producer=AIOKafkaProducer(bootstrap_servers=os.environ['KAFKA_BOOTSTRAP']);await producer.start()
        yield
        if producer: await producer.stop()
        await cache.aclose()
    app=FastAPI(lifespan=lifespan)
    @app.get('/health')
    async def health(): return {'role':config['role'],'scope':schema}
    @app.get('/products')
    async def products():
        if config['role']!='inventory': raise HTTPException(404)
        key=schema+':catalog'
        saved=await cache.get(key) if config['redis_enabled'] else None
        if saved: return json.loads(saved)
        rows=await query('SELECT id,name,price,stock FROM products ORDER BY id')
        try: rows=[functions['inventory'](row) for row in rows]
        except ValueError as exc: raise HTTPException(503,'invalid catalog record') from exc
        if config['redis_enabled']: await cache.set(key,json.dumps(rows),ex=30)
        return rows
    @app.post('/charge')
    async def charge(payload:dict):
        if config['role']!='payment': raise HTTPException(404)
        try: amount=functions['payment'](payload['amount'])
        except ValueError as exc: raise HTTPException(422,'invalid amount') from exc
        await query('INSERT INTO payments(order_id,amount) VALUES(%s,%s)',(payload['order_id'],amount))
        return {'status':'charged'}
    @app.post('/checkout')
    async def checkout(payload:dict):
        if config['role']!='order': raise HTTPException(404)
        async with httpx.AsyncClient(timeout=3) as client:
            response=await client.get(config['urls']['inventory']+'/products')
            if response.status_code!=200: raise HTTPException(502,'catalog dependency rejected request')
            try: item=functions['order'](response.json())
            except ValueError as exc: raise HTTPException(409,'catalog unavailable') from exc
            amount=functions['pricing'](item['price'],1,payload.get('discount',0))
            oid=str(uuid.uuid4())
            response=await client.post(config['urls']['payment']+'/charge',json={'order_id':oid,'amount':amount})
            if response.status_code!=200: raise HTTPException(502,'payment dependency rejected request')
            await query('INSERT INTO orders(id,total) VALUES(%s,%s)',(oid,amount))
            if producer: await producer.send_and_wait(config['topic'],json.dumps({'order_id':oid,'total':amount}).encode())
            return {'order_id':oid,'total':amount}
    return app

if __name__=='__main__':
    # Bound every process executing candidate code, including the HTTP replay.
    from .patching import limits
    limits()
    import uvicorn
    settings=json.loads(Path(sys.argv[1]).read_text())
    uvicorn.run(create_app(settings),host='127.0.0.1',port=settings['port'],log_level='critical',access_log=False)
