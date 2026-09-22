"""Bounded continuous real traffic, enabled/disabled through Sentinel."""
import asyncio
import httpx
from .runtime import redis

async def worker():
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            if await redis.get('traffic:enabled') != '0':
                try:
                    await client.get('http://gateway:8000/products')
                    await client.post('http://gateway:8000/checkout')
                except httpx.HTTPError:
                    pass
            await asyncio.sleep(.7)

async def main():
    await asyncio.gather(*(worker() for _ in range(3)))

asyncio.run(main())
