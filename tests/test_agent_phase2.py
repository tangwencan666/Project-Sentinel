"""Protocol fault server is a labelled failure harness, never an AI evaluation substitute."""
import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import ast
import difflib
import httpx
import pytest
from sentinel.provider import request_once,ProviderError,usage_values
from sentinel.security import redact
from sentinel.ai_patching import apply_diff
from sentinel.contracts import validate_diagnosis,check_citations
from sentinel.patching import propose

class FaultHandler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        mode=self.path.split('/')[1]
        if mode=='timeout': time.sleep(.2)
        status=int(mode) if mode.isdigit() else 200
        self.send_response(status);self.end_headers()
        try: self.wfile.write(b'not-json' if mode=='invalid' else b'{}')
        except BrokenPipeError: pass

@pytest.mark.parametrize('mode,code,retryable',[('429','PROVIDER_HTTP_ERROR',True),('500','PROVIDER_HTTP_ERROR',True),('401','PROVIDER_HTTP_ERROR',False),('invalid','INVALID_PROVIDER_JSON',False),('timeout','LLM_TIMEOUT',True)])
def test_real_http_provider_failures(mode,code,retryable):
    server=ThreadingHTTPServer(('127.0.0.1',0),FaultHandler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    async def run():
        cfg={'LLM_BASE_URL':f'http://127.0.0.1:{server.server_port}/{mode}','LLM_MODEL':'protocol-fault-harness','LLM_API_KEY':'test-not-real','LLM_TIMEOUT_SECONDS':'.05'}
        async with httpx.AsyncClient() as client:
            with pytest.raises(ProviderError) as error: await request_once(client,cfg,[{'role':'user','content':'test'}])
            assert error.value.code==code
            assert error.value.retryable==retryable
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

def test_usage_unknown_is_not_zero_or_estimated():
    assert usage_values({}, {})==(None,None,None,None,None)
    assert usage_values({'usage':{'prompt_tokens':4,'completion_tokens':2,'total_tokens':6}}, {})==(4,2,6,None,None)

def test_secrets_are_masked(monkeypatch):
    monkeypatch.setenv('LLM_API_KEY','synthetic-secret-for-unit-test')
    assert redact({'api_key':'x'})['api_key']=='[REDACTED]'
    assert 'abc123' not in redact('Authorization: Bearer abc123')
    assert 'password=pwd' not in redact('password=pwd')

@pytest.mark.parametrize('path',['../.env','/app/.env','sentinel/scenarios.py','services/app.py','docs/verification.json'])
def test_source_boundary(path):
    from sentinel.tool_registry import read_source
    with pytest.raises(ValueError): read_source(path)

def test_patch_path_and_context_are_enforced():
    base=Path('/app/services/pricing.py').read_text()
    candidate=base.replace('(1 - discount)','(1 - (discount or 0))')
    diff=''.join(difflib.unified_diff(base.splitlines(True),candidate.splitlines(True),fromfile='a/services/pricing.py',tofile='b/services/pricing.py'))
    assert apply_diff(base,diff)==candidate
    assert apply_diff(base,diff.rstrip('\n'))==candidate
    with pytest.raises(ValueError): apply_diff(base,diff.replace('services/pricing.py','../.env'))
    with pytest.raises(ValueError): apply_diff(base,diff.replace('round(price','round(other'))

def test_failed_tests_reject_candidate():
    candidate='def total(price, quantity, discount=0):\n    return 0\n'
    result=propose(candidate,'phase2-failed-tests')
    assert result['candidate_test']['exit_code']!=0
    assert result['validated'] is False

def test_unknown_or_cross_run_evidence_rejected():
    with pytest.raises(ValueError): check_citations(['E-other'],[{'id':'E-current','kind':'logs'}])
    with pytest.raises(ValueError): check_citations(['E-one','E-two'],[{'id':'E-one','kind':'logs'},{'id':'E-two','kind':'logs'}],2)

def test_investigator_imports_never_reach_evaluator_or_scenarios():
    files=['agent.py','tool_registry.py','evidence.py','provider.py','contracts.py','storage.py','security.py','baseline.py','patching.py','ai_patching.py','sandbox_server.py','recovery.py']
    for file in files:
        tree=ast.parse(Path('/app/sentinel',file).read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom): assert not any(x in (node.module or '') for x in ('scenarios','evaluator'))
        assert 'ground_truth_root_cause' not in Path('/app/sentinel',file).read_text(encoding='utf-8-sig')

def test_invalid_tool_is_audited_not_executed():
    from services.runtime import pool,query
    from sentinel.storage import migrate
    from sentinel.tool_registry import execute_tool
    import uuid
    async def run():
        await pool.open();await migrate()
        incident,run_id=str(uuid.uuid4()),str(uuid.uuid4())
        await query("INSERT INTO incidents(id,status,signal) VALUES(%s,'test','{}')",(incident,))
        await query("INSERT INTO investigation_runs(id,incident_id,mode,status) VALUES(%s,%s,'TEST','completed')",(run_id,incident))
        a=await execute_tool('execute_shell',{'command':'must-never-run'},incident,run_id)
        b=await execute_tool('read_source_file',{'path':'services/pricing.py','extra':True},incident,run_id)
        c=await execute_tool('submit_verification',{},incident,run_id,'Investigator')
        assert a['error'] and b['error'] and c['error'] and not a['evidence_ids']
        rows=await query('SELECT status,finished_at FROM tool_calls WHERE run_id=%s',(run_id,))
        assert len(rows)==3 and all(r['status']=='failed' and r['finished_at'] for r in rows)
        await pool.close()
    asyncio.run(run())

def test_context_compaction_preserves_tool_protocol_and_citations():
    from sentinel.agent import compact_context
    messages=[{'role':'system','content':'unchanged'}]
    for n in range(10):
        messages.extend([{'role':'assistant','tool_calls':[{'id':str(n)}]}, {'role':'tool','tool_call_id':str(n),'content':json.dumps({'evidence_ids':['E-0123456789abcdef'],'result':{'observation':'x'*6000}})}])
    assert compact_context(messages,30000)>0
    assert len(json.dumps(messages))<30000
    for message in messages:
        if message['role']=='tool': assert json.loads(message['content'])['evidence_ids']==['E-0123456789abcdef']
    assert messages[0]['content']=='unchanged'

def test_database_observer_does_not_count_its_own_sql():
    from sentinel.evidence import database
    async def run():
        await database()
        result=await database()
        assert result['statements']
        assert all('pg_stat_' not in s['query'].lower() for s in result['statements'])
    asyncio.run(run())

def test_query_deltas_use_query_identity_not_normalized_text():
    from sentinel.tool_registry import statement_deltas
    before=[{'userid':1,'dbid':1,'queryid':101,'query':'SELECT pg_sleep($1)','calls':500},{'userid':1,'dbid':1,'queryid':102,'query':'SELECT pg_sleep($1)','calls':20}]
    after=[{**before[0],'calls':500},{**before[1],'calls':23},{**before[0],'queryid':103,'calls':900}]
    assert [r['calls_delta'] for r in statement_deltas(before,after)]==[0,3,None]
    assert statement_deltas(before,[{**before[0],'calls':0}])[0]['calls_delta'] is None

def test_recovery_requires_current_pending_run_and_observation_window(monkeypatch):
    import services.runtime as runtime
    from services.runtime import query
    from psycopg_pool import AsyncConnectionPool
    from psycopg.rows import dict_row
    from sentinel.storage import migrate
    from sentinel.recovery import capture_after
    import uuid
    async def run():
        pool=AsyncConnectionPool(runtime.DSN,open=False,kwargs={'autocommit':True,'row_factory':dict_row})
        monkeypatch.setattr(runtime,'pool',pool)
        await pool.open();await migrate()
        iid,rid=str(uuid.uuid4()),str(uuid.uuid4())
        await query("INSERT INTO incidents(id,status,signal,investigation_run) VALUES(%s,'awaiting_recovery','{}',%s)",(iid,rid))
        await query("INSERT INTO investigation_runs(id,incident_id,mode,status) VALUES(%s,%s,'TEST','started')",(rid,iid))
        with pytest.raises(ValueError,match='no pending'): await capture_after(iid,rid)
        await query("INSERT INTO recovery_checks(run_id,incident_id,status,payload) VALUES(%s,%s,'awaiting_recovery','{}')",(rid,iid))
        with pytest.raises(ValueError,match='22-second'): await capture_after(iid,rid)
        await query("UPDATE incidents SET status='test' WHERE id=%s",(iid,))
        await query("UPDATE investigation_runs SET status='completed',finished_at=now() WHERE id=%s",(rid,))
        await pool.close()
    asyncio.run(run())
