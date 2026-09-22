"""Synthetic transient-dependency regression; not an Agent accuracy trial."""
import asyncio
import pytest
from redis.exceptions import ConnectionError


def test_inventory_worker_survives_transient_redis_failure(monkeypatch):
    from services import app

    async def run():
        recovered=asyncio.Event()
        attempts=0

        async def transient_fault(name):
            nonlocal attempts
            attempts+=1
            if attempts==1:
                raise ConnectionError('synthetic transient DNS failure')
            recovered.set()
            return False

        monkeypatch.setattr(app,'SERVICE','inventory-service')
        monkeypatch.setattr(app,'fault',transient_fault)
        task=asyncio.create_task(app.exhaust())
        try:
            await asyncio.wait_for(recovered.wait(),2.5)
            assert attempts>=2 and not task.done()
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(run())
