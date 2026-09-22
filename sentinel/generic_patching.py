"""Path-selected patch profiles for pure business functions, never fault labels.

The controller owns I/O, fixtures, contracts and workspaces. Candidate code cannot
import, inspect attributes, run subprocesses or call arbitrary functions. This is
a bounded candidate capability, not a general untrusted-Python execution service.
"""
import ast
import asyncio
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid
from .patching import limits

ROOT=Path('/app')
PROFILES={
    'services/pricing.py':{'component':'pricing','symbol':'total','contract':'tests/pricing_contract.py','services':['order','inventory','payment']},
    'services/payment.py':{'component':'payment','symbol':'normalize_amount','contract':'tests/domain_contract.py','services':['order','inventory','payment']},
    'services/order.py':{'component':'order','symbol':'choose_item','contract':'tests/domain_contract.py','services':['order','inventory','payment']},
    'services/inventory.py':{'component':'inventory','symbol':'normalize_product','contract':'tests/domain_contract.py','services':['order','inventory','payment']},
}
DENIED_PARTS={'.env','secrets','evaluation','benchmarks','scenarios.py','evaluator.py','tests','infra','compose.yaml'}
CALLS={'round','float','int','str','len','isinstance','ValueError'}
NODES=(ast.Module,ast.FunctionDef,ast.arguments,ast.arg,ast.Expr,ast.Constant,ast.Return,ast.If,
       ast.IfExp,ast.Raise,ast.Assign,ast.Name,ast.Load,ast.Store,ast.BinOp,ast.UnaryOp,ast.BoolOp,
       ast.Compare,ast.Call,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Or,ast.And,ast.Lt,ast.LtE,ast.Gt,
       ast.GtE,ast.Eq,ast.NotEq,ast.Is,ast.IsNot,ast.Not,ast.USub,ast.BitOr,ast.Dict,ast.List,
       ast.Tuple,ast.Subscript,ast.In,ast.NotIn)

def allowed_path(path):
    if '\\' in path or any(part in DENIED_PARTS or part in ('.','..') for part in path.split('/')):
        raise ValueError('Protected path or traversal rejected')
    if path not in PROFILES: raise ValueError('No approved candidate profile for this path')
    real=ROOT/path
    if real.is_symlink() or not real.resolve().is_relative_to(ROOT.resolve()): raise ValueError('Symlink/traversal rejected')
    return PROFILES[path]

def validate_source(path,source,base=None):
    profile=allowed_path(path)
    if len(source)>8000: raise ValueError('Candidate source too large')
    tree=ast.parse(source);original=ast.parse(base if base is not None else (ROOT/path).read_text())
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    baseline=[n for n in original.body if isinstance(n,ast.FunctionDef)]
    if len(functions)!=1 or functions[0].name!=profile['symbol'] or len(baseline)!=1:
        raise ValueError('Only the approved business function may be defined')
    fn=functions[0]
    if ast.dump(fn.args)!=ast.dump(baseline[0].args): raise ValueError('Function signature/defaults are immutable')
    if (ast.dump(fn.returns) if fn.returns is not None else None)!=(ast.dump(baseline[0].returns) if baseline[0].returns is not None else None):
        raise ValueError('Return annotation is immutable')
    if fn.decorator_list or fn.args.vararg or fn.args.kwarg or fn.args.kwonlyargs or fn.args.posonlyargs:
        raise ValueError('Decorators and variadic signatures forbidden')
    if sum(isinstance(n,ast.FunctionDef) for n in ast.walk(tree))!=1: raise ValueError('Nested functions forbidden')
    for node in ast.walk(tree):
        if not isinstance(node,NODES): raise ValueError('Unsupported candidate syntax: '+type(node).__name__)
        if isinstance(node,ast.Name) and node.id.startswith('_'): raise ValueError('Private names forbidden')
        if isinstance(node,ast.Call) and (not isinstance(node.func,ast.Name) or node.func.id not in CALLS):
            raise ValueError('Candidate call forbidden')
        if isinstance(node,ast.Constant) and isinstance(node.value,(str,bytes)) and len(node.value)>2000:
            raise ValueError('Oversized constant')
    for node in tree.body:
        if not isinstance(node,(ast.FunctionDef,ast.Expr)) or isinstance(node,ast.Expr) and not isinstance(node.value,ast.Constant):
            raise ValueError('Module side effects forbidden')
    return hashlib.sha256(source.encode()).hexdigest()

def apply_file_diff(base,diff,path):
    allowed_path(path)
    lines=(diff if diff.endswith('\n') else diff+'\n').splitlines(keepends=True)
    if lines and lines[0].startswith('diff --git '):
        if lines[0].strip()!=f'diff --git a/{path} b/{path}': raise ValueError('Diff path mismatch')
        lines=lines[1:]
        if lines and lines[0].startswith('index '): lines=lines[1:]
    if len(lines)<3 or lines[0].strip()!=f'--- a/{path}' or lines[1].strip()!=f'+++ b/{path}':
        raise ValueError('Diff path mismatch; tests and policy files are protected')
    original=base.splitlines(keepends=True);out=[];cursor=0;i=2
    while i<len(lines):
        match=re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\n]*\n?',lines[i])
        if not match: raise ValueError('Invalid hunk')
        old_start,old_count,new_start,new_count=match.groups();start=int(old_start)-1
        if start<cursor or start>len(original): raise ValueError('Overlapping/out-of-range hunk')
        out+=original[cursor:start];cursor=start;i+=1;old_seen=new_seen=0
        if int(new_start)!=len(out)+1: raise ValueError('New hunk position mismatch')
        while i<len(lines) and not lines[i].startswith('@@ '):
            line=lines[i];i+=1
            if not line or line[0] not in (' ','+','-'): raise ValueError('Invalid diff line')
            marker,content=line[0],line[1:]
            if marker in (' ','-'):
                if cursor>=len(original) or original[cursor]!=content: raise ValueError('Context does not match immutable base')
                cursor+=1;old_seen+=1
            if marker in (' ','+'): out.append(content);new_seen+=1
        if old_seen!=int(old_count or 1) or new_seen!=int(new_count or 1): raise ValueError('Hunk length mismatch')
    out+=original[cursor:];source=''.join(out)
    if source==base: raise ValueError('Empty patch')
    validate_source(path,source,base)
    return source

def parse_diff(diff):
    if len(diff)>16000: raise ValueError('Diff too large')
    headers=re.findall(r'^--- a/(.+)$',diff,re.M)
    if len(headers)!=1: raise ValueError('Current candidate policy permits exactly one business file per proposal')
    path=headers[0].strip();profile=allowed_path(path);base=(ROOT/path).read_text()
    source=apply_file_diff(base,diff,path)
    return path,profile,base,source

def source_to_diff(path,source):
    """Serialize model-written source into an exact diff; never changes model logic."""
    allowed_path(path)
    if not isinstance(source,str) or len(source)>8000: raise ValueError('Invalid candidate source')
    if not source.endswith('\n'): source+='\n'
    return ''.join(difflib.unified_diff((ROOT/path).read_text().splitlines(True),source.splitlines(True),
                                      fromfile='a/'+path,tofile='b/'+path))

def risk(diff,path):
    added=sum(line.startswith('+') and not line.startswith('+++') for line in diff.splitlines())
    removed=sum(line.startswith('-') and not line.startswith('---') for line in diff.splitlines())
    financial=path in ('services/payment.py','services/pricing.py')
    return {'level':'HIGH' if financial or added+removed>25 else 'MEDIUM',
        'changed_lines':added+removed,'files':1,'api_contract':'Signature preserved; behavioral compatibility limited to tested inputs',
        'db_schema':'forbidden','concurrency':'candidate loops/async/threads forbidden',
        'security':'financial calculation' if financial else 'input validation / catalog integrity',
        'infrastructure':'changes forbidden','automatic_apply_allowed':False,
        'reason':'Money handling or broad edit requires human review' if financial or added+removed>25 else 'Business behavior change requires human review'}

def run_unit(path,source,directory):
    profile=PROFILES[path];directory.mkdir(parents=True,exist_ok=True)
    target=directory/Path(path).name;target.write_text(source)
    contract=(ROOT/profile['contract']).read_bytes();test=directory/'test_contract.py';test.write_bytes(contract)
    env={'PATH':os.environ['PATH'],'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1',
         'PATCH_COMPONENT':profile['component'],'PATCH_SOURCE':str(target)}
    result=subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider',str(test)],
        cwd=directory,env=env,text=True,capture_output=True,timeout=12,preexec_fn=limits if os.name=='posix' else None)
    if test.read_bytes()!=contract: raise ValueError('Immutable test contract changed')
    return {'exit_code':result.returncode,'output':result.stdout+result.stderr,
            'contract_sha256':hashlib.sha256(contract).hexdigest()}

async def validate_candidate(diff,incident_id,origin='AI_GENERATED'):
    if origin not in ('AI_GENERATED','TEST_FIXTURE','HUMAN'): raise ValueError('Unknown candidate origin')
    path,profile,base,source=parse_diff(diff);digest=hashlib.sha256(source.encode()).hexdigest()
    directory=Path('/work')/'generic'/str(uuid.UUID(str(incident_id)))/digest
    before=await asyncio.to_thread(run_unit,path,base,directory/'baseline')
    after=await asyncio.to_thread(run_unit,path,source,directory/'candidate')
    result={'origin':origin,'path':path,'profile':profile['component'],'submitted_diff':diff,
        'source':source,'sha256':digest,'base_sha256':hashlib.sha256(base.encode()).hexdigest(),
        'baseline_test':before,'candidate_test':after,'risk':risk(diff,path),
        'candidate_verified':False,'production_applied':False,'automatic_apply_allowed':False,
        'status':'TESTS_FAILED','sandbox_scope':'Three isolated HTTP processes with dedicated PostgreSQL schema and Redis namespace; shared host container/kernel, not a hostile-code VM.'}
    if after['exit_code'] or before['exit_code']==0: return result
    from .multiservice_sandbox import replay
    old=await replay(profile['component'],path,directory/'baseline'/Path(path).name)
    new=await replay(profile['component'],path,directory/'candidate'/Path(path).name)
    passed=old['business_violation_pct']>0 and new['business_violation_pct']==0 and new['healthy_control_passed']
    result.update(replay={'before':old,'after':new,'passed':passed},candidate_verified=passed,
                  validated=passed,status='CANDIDATE_VERIFIED' if passed else 'REPLAY_FAILED')
    return result
