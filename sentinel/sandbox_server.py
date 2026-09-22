"""Fixed integration harness. Candidate can only provide the validated pricing function.
Reuses live inventory over HTTP; does not write payments/orders or alter deployed code.
"""
import importlib.util
import os
from fastapi import FastAPI
import httpx

spec=importlib.util.spec_from_file_location('candidate_pricing',os.environ['PRICING_SOURCE'])
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
app=FastAPI()

@app.get('/health')
def health(): return {'ready':True}

@app.post('/checkout')
async def checkout(payload:dict):
    async with httpx.AsyncClient(timeout=4) as client:
        response=await client.get('http://inventory-service:8000/products')
        response.raise_for_status();price=response.json()[0]['price']
    try:
        amount=module.total(price,1,payload.get('discount'))
        if not isinstance(amount,(float,int)) or amount<0: raise ValueError('invalid calculated total')
        return {'total':amount,'inventory_price':price}
    except Exception as exc:
        from fastapi.responses import JSONResponse
        return JSONResponse({'error':type(exc).__name__},status_code=500)
