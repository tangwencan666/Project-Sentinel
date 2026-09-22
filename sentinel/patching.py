"""Narrow patch capability: arithmetic-only pricing module, immutable tests, no arbitrary shell."""
import ast
import hashlib
import difflib
import os
from pathlib import Path
import subprocess
import sys

BASE = Path('/app/services/pricing.py')
ALLOWED = (ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Expr,ast.Constant,ast.Return,ast.If,ast.IfExp,ast.Raise,ast.Assign,ast.Name,ast.Load,ast.Store,ast.BinOp,ast.UnaryOp,ast.BoolOp,ast.Compare,ast.Call,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Or,ast.And,ast.Lt,ast.LtE,ast.Gt,ast.GtE,ast.Eq,ast.NotEq,ast.Is,ast.IsNot,ast.Not,ast.USub,ast.BitOr)

def validate(source):
    if len(source)>8000: raise ValueError('patch too large')
    tree=ast.parse(source)
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    if len(functions)!=1 or functions[0].name!='total': raise ValueError('only total() may be defined')
    fn=functions[0]
    if fn.decorator_list or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.posonlyargs: raise ValueError('unsupported function signature')
    if [a.arg for a in fn.args.args]!=['price','quantity','discount']: raise ValueError('pricing signature must be preserved')
    if any(not isinstance(d,ast.Constant) or d.value not in (0,None) for d in fn.args.defaults): raise ValueError('unsafe defaults')
    if sum(isinstance(n,ast.FunctionDef) for n in ast.walk(tree))!=1: raise ValueError('nested functions forbidden')
    for node in ast.walk(tree):
        if not isinstance(node,ALLOWED): raise ValueError(f'unsupported syntax: {type(node).__name__}')
        if isinstance(node,ast.Name) and node.id.startswith('_'): raise ValueError('private names forbidden')
        if isinstance(node,ast.Call) and (not isinstance(node.func,ast.Name) or node.func.id not in ('round','ValueError','float')): raise ValueError('call forbidden')
    for node in tree.body:
        if not isinstance(node,(ast.FunctionDef,ast.Expr)): raise ValueError('module side effects forbidden')
        if isinstance(node,ast.Expr) and not isinstance(node.value,ast.Constant): raise ValueError('module expressions forbidden')
    return hashlib.sha256(source.encode()).hexdigest()

def limits():
    import resource
    resource.setrlimit(resource.RLIMIT_CPU,(3,3))
    resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
    resource.setrlimit(resource.RLIMIT_FSIZE,(1024*1024,1024*1024))

def test_source(source, directory):
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'pricing.py').write_text(source)
    (directory/'test_pricing.py').write_text(Path('/app/tests/pricing_contract.py').read_text())
    run=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','test_pricing.py'],cwd=directory,capture_output=True,text=True,timeout=12,env={'PATH':os.environ['PATH'],'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'},preexec_fn=limits if os.name=='posix' else None)
    return {'exit_code':run.returncode,'output':(run.stdout+run.stderr)[-12000:]}

def propose(source, incident_id):
    digest=validate(source)
    base=BASE.read_text()
    directory=Path('/work')/str(incident_id)/digest
    baseline=test_source(base,directory/'baseline')
    candidate=test_source(source,directory/'candidate')
    return {'sha256':digest,'base_sha256':hashlib.sha256(base.encode()).hexdigest(),'diff':''.join(difflib.unified_diff(base.splitlines(True),source.splitlines(True),fromfile='a/services/pricing.py',tofile='b/services/pricing.py')),'baseline_test':baseline,'candidate_test':candidate,'validated':baseline['exit_code']!=0 and candidate['exit_code']==0,'source':source}
