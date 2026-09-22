"""Narrow checks for the two declared operational changes after the frozen evaluation."""
import ast


def api_default_only(before,after):
    return before.count(b"='HYBRID_V3'")==3 and before.replace(b"='HYBRID_V3'",b"='HYBRID_V2'")==after


def worker_recovery_only(before,after):
    old=ast.parse(before);new=ast.parse(after)
    additions=[n for n in new.body if isinstance(n,ast.ImportFrom) and n.module=='redis.exceptions']
    if len(additions)!=1 or [(a.name,a.asname) for a in additions[0].names]!=[('RedisError',None)]:return False
    new.body.remove(additions[0])
    function=next(n for n in new.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='exhaust')
    loop=next(n for n in function.body if isinstance(n,ast.While))
    if len(loop.body)!=1 or not isinstance(loop.body[0],ast.Try):return False
    wrapper=loop.body[0]
    expected=ast.parse('try:\n    pass\nexcept RedisError:\n    await asyncio.sleep(1)\n').body[0]
    if wrapper.orelse or wrapper.finalbody or len(wrapper.handlers)!=1:return False
    if ast.dump(wrapper.handlers[0])!=ast.dump(expected.handlers[0]):return False
    loop.body=wrapper.body
    return ast.dump(old)==ast.dump(new)
