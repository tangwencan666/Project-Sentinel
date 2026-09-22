"""Supervised dependency workers expose readiness instead of silently exiting."""
import asyncio
import logging

async def supervise(factory, process, status, *, initial_delay=.5, maximum_delay=10):
    delay=initial_delay
    while True:
        resource=None
        status.update(ready=False)
        try:
            resource=factory()
            await resource.start()
            status.update(ready=True,last_error=None)
            delay=initial_delay
            await process(resource)
            raise RuntimeError('Background stream ended unexpectedly')
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            status.update(ready=False,last_error=type(exc).__name__,restarts=status.get('restarts',0)+1)
            logging.getLogger(__name__).warning('Background consumer reconnect: %s',type(exc).__name__)
        finally:
            status['ready']=False
            if resource:
                try: await asyncio.wait_for(resource.stop(),5)
                except Exception: logging.getLogger(__name__).warning('Background consumer cleanup failed')
        await asyncio.sleep(delay)
        delay=min(delay*2,maximum_delay)
