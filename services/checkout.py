"""Business checkout orchestration; experiment controls remain outside this module."""
import json
import uuid
from fastapi import HTTPException
from opentelemetry import propagate
from .order import choose_item

async def checkout(items, discount, pricing, downstream, query, producer):
    try: item=choose_item(items)
    except ValueError as exc: raise HTTPException(409,'catalog unavailable') from exc
    amount=pricing(item['price'],1,discount)
    order_id=str(uuid.uuid4())
    await downstream('payment-service','/charge',{'order_id':order_id,'amount':amount})
    await query('INSERT INTO orders(id,user_id,total) VALUES(%s,1,%s)',(order_id,amount))
    carrier={};propagate.inject(carrier)
    await producer.send_and_wait('orders',json.dumps({'order_id':order_id,'trace':carrier}).encode())
    return {'order_id':order_id,'total':amount}
