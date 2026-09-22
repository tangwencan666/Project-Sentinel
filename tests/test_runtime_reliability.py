"""Protocol/recovery tests, NOT RCA accuracy. Real PostgreSQL, Redis and local HTTP.

Synthetic provider payloads are deliberately malformed boundary fixtures; they never
enter benchmark results or claim to represent DeepSeek reasoning performance.
"""
import ast
import asyncio
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import uuid
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool
import services.runtime as database
from sentinel import checkpoints, runtime_tools, provider
from sentinel.storage import migrate, evidence_for
from sentinel.runtime_state import (InvestigationState, ToolError, RuntimeFailure, Budgets,
    offered_names, readiness, transition)
from sentinel.structured_output import structured, planner_fallback
from sentinel.hybrid_tools import InvestigationPlan

E1='E-0123456789abcdef';E2='E-1123456789abcdef'

def state(): return InvestigationState(run_id=str(uuid.uuid4()),incident_id=str(uuid.uuid4()))
def hypothesis(status='CREATED'):
    return {'hypothesis_id':'H-boundary','status':status,'hypothesis':'Observed test boundary',
            'affected_service':'order-service','evidence_ids':[E1,E2],
            'reasoning_summary':'Protocol fixture, no accuracy claim.','next_evidence_needed':''}
def error(): return ToolError(error_code='SYMBOL_NOT_FOUND',message='Actual symbol absent',expected=['total'])

@asynccontextmanager
async def real_run(monkeypatch):
    import redis.asyncio as redis_async
    from sentinel import evidence as adapters
    redis_client=redis_async.from_url('redis://redis:6379',decode_responses=True)
    monkeypatch.setattr(adapters,'redis',redis_client)
    pool=AsyncConnectionPool(database.DSN,open=False,kwargs={'autocommit':True,'row_factory':dict_row})
    monkeypatch.setattr(database,'pool',pool)
    await pool.open();await migrate();s=state()
    await database.query("INSERT INTO incidents(id,status,signal) VALUES(%s,'test','{}')",(s.incident_id,))
    await database.query("INSERT INTO investigation_runs(id,incident_id,mode,status) VALUES(%s,%s,'RELIABILITY_TEST','completed')",(s.run_id,s.incident_id))
    async def persist(): await checkpoints.save(s.incident_id,s.run_id,s.phase,s.model_dump())
    try: yield s,persist
    finally:
        await pool.close()
        await redis_client.aclose()

def test_01_error_survives_context_reconstruction():
    s=state();s.pin_error('get_code_symbol',error())
    rebuilt=s.rebuild({'items':[]})
    assert rebuilt['P0']['validation_errors']['get_code_symbol']['expected']==['total']

def test_02_validation_pinned_when_history_discarded():
    s=state();s.pin_error('get_code_symbol',error());s.history=[{'old':'x'*5000}]*4
    context=s.rebuild({},limit=4000)
    assert not context['P3'] and context['P0']['validation_errors']

def test_03_illegal_transition_can_be_corrected():
    s=state()
    with pytest.raises(RuntimeFailure) as caught: s.apply_hypothesis(hypothesis('UPDATED'))
    assert caught.value.error.expected=={'allowed':['CREATED']}
    assert not s.active_hypotheses
    s.apply_hypothesis(hypothesis());s.apply_hypothesis(hypothesis('SUPPORTED'))
    assert s.active_hypotheses['H-boundary']['status']=='SUPPORTED'

def test_04_unread_citation_directs_real_read_then_ready():
    s=state();s.apply_hypothesis(hypothesis());s.read_registry={E1:{},E2:{}}
    ev=[{'id':E1},{'id':E2}]
    candidate={'evidence_ids':[E1,E2],'affected_service':'order-service','code_locations':[{'path':'services/pricing.py','start_line':3,'end_line':6}]}
    missing=readiness(s,candidate,ev)
    assert missing[0]['error_code']=='UNREAD_CITATION' and missing[0]['required_tool']=='read_source_file'
    actual=runtime_tools.registry.read_source(**missing[0]['suggested_arguments'])
    runtime_tools.register_read(s,{'id':'source','kind':'read_source_file','payload':actual})
    assert readiness(s,candidate,ev)==[]

PLAN={'suspected_services':['order-service'],'initial_hypotheses':['unconfirmed'],
      'tool_priority':['read_evidence'],'stop_conditions':['independent corroboration']}

def repair_fixture(outputs,stage='Planner'):
    async def run():
        s=state();events=[];calls=[]
        async def invoke(messages):
            calls.append(messages);return {'content':outputs[len(calls)-1]}
        async def persist():
            # Round trip on every checkpoint to detect unserializable state.
            InvestigationState.model_validate_json(s.model_dump_json())
        async def record(kind,payload): events.append((kind,payload))
        result=await structured([{'role':'system','content':'Return JSON'},{'role':'user','content':'fixture'}],InvestigationPlan,invoke,s,stage,persist,record)
        return result,s,events,calls
    return asyncio.run(run())

def test_05_invalid_json_repaired_with_exact_parse_error():
    result,s,events,calls=repair_fixture(['{"unfinished":',json.dumps(PLAN)])
    assert result==PLAN and len(calls)==2 and s.budgets.used=={'schema_repair':1}
    assert 'INVALID_ARGUMENT_JSON' in calls[1][1]['content']

def test_06_wrong_schema_repaired_with_field_locations():
    result,s,events,calls=repair_fixture([json.dumps(InvestigationPlan.model_json_schema()),json.dumps(PLAN)])
    assert result==PLAN and 'suspected_services' in calls[1][1]['content'] and not s.validation_errors

def test_07_planner_repair_bounded_then_explicit_fallback():
    with pytest.raises(RuntimeFailure): repair_fixture(['{}','{}','{}'])
    plan=planner_fallback({'signals':[{'signal':'measured anomaly','suspected_services':['notification-service']}], 'suspected_services':[]})
    assert plan['suspected_services']==['notification-service'] and InvestigationPlan.model_validate(plan)

def test_08_repeated_failure_blocks_third_identical_call():
    s=state();args={'symbol':'absent'};e=error().model_dump()
    s.observe_failure('get_code_symbol',args,e);assert s.breaker('get_code_symbol',args) is None
    s.observe_failure('get_code_symbol',args,e)
    assert s.breaker('get_code_symbol',args).error_code=='CIRCUIT_BREAKER'
    assert s.breaker('get_code_symbol',{'symbol':'total'}) is None

def test_09_correction_does_not_consume_exploration():
    b=Budgets();b.consume('correction');b.consume('schema_repair')
    assert b.used.get('exploration',0)==0

def test_10_soft_convergence_preserves_evidence_and_correction():
    s=state();s.budgets.used['exploration']=16
    allowed=offered_names(s,runtime_tools.NAMES)
    assert {'read_evidence','read_source_file','get_trace_detail','record_hypothesis','inspect_database'}<=allowed
    assert 'get_trace' not in allowed and s.convergence=='SOFT_CONVERGENCE'

def test_11_critical_evidence_survives_history_compression():
    s=state();s.critical_evidence[E1]={'sql':'SELECT pg_sleep(2)','observed':4};s.recent_results=[{'large':'x'*20000}]*8
    assert s.rebuild({},4000)['P1']['critical_evidence'][E1]['observed']==4

def test_12_detail_tool_preserves_full_payload():
    s=state();detail={'evidence_ids':[E1],'result':{'spans':[{'detail':'x'*9000}],'tail':'not omitted'}}
    actual=asyncio.run(runtime_tools.model_result(s,'get_trace_detail',detail))
    assert actual==detail and actual['result']['tail']=='not omitted'

class BoundaryServer(BaseHTTPRequestHandler):
    responses=[];requests=[]
    def log_message(self,*args): pass
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        type(self).requests.append(body)
        status,payload=type(self).responses.pop(0)
        self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

def local_provider(monkeypatch,responses):
    BoundaryServer.responses=list(responses);BoundaryServer.requests=[]
    server=ThreadingHTTPServer(('127.0.0.1',0),BoundaryServer)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    monkeypatch.setattr(provider,'configuration',lambda:{'LLM_MODEL':'synthetic-boundary-fixture','LLM_API_KEY':'synthetic-test-only',
        'LLM_BASE_URL':f'http://127.0.0.1:{server.server_port}','LLM_MAX_OUTPUT_TOKENS':'2500'})
    return server

def provider_payload(finish='length'):
    return {'id':'boundary-request','choices':[{'finish_reason':finish,'message':{'role':'assistant','content':'{"partial":'}}],
            'usage':{'prompt_tokens':40,'completion_tokens':2500,'total_tokens':2540}}

def test_13_provider_finish_reason_persisted_in_real_database(monkeypatch):
    server=local_provider(monkeypatch,[(200,provider_payload())])
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            response=await provider.complete(s.incident_id,s.run_id,'ProtocolFixture',[{'role':'user','content':'fixture'}],include_metadata=True)
            row=await database.query('SELECT diagnostics FROM llm_calls WHERE id=%s',(response['_runtime']['call_id'],),one=True)
            assert row['diagnostics']['finish_reason']=='length' and row['diagnostics']['request_id']=='boundary-request'
            assert row['diagnostics']['raw_output_length']>0 and row['diagnostics']['latency_seconds']>0
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

@pytest.mark.parametrize('field', ['unfinished_actions','active_hypotheses','validation_errors'])
def test_14_15_16_real_checkpoint_restores_control_state(monkeypatch,field):
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            s.unfinished_actions=[{'id':'unfinished','function':{'name':'inspect_redis','arguments':'{}'}}]
            s.apply_hypothesis(hypothesis());s.pin_error('get_code_symbol',error());await persist()
            loaded=InvestigationState.model_validate((await checkpoints.load(s.run_id))['payload'])
            assert getattr(loaded,field)==getattr(s,field)
    asyncio.run(run())

def test_17_missing_requirements_direct_next_action():
    s=state();missing=readiness(s,{'affected_service':'order-service','evidence_ids':[]},[])
    assert missing[0]['required_tool']=='record_hypothesis' and missing[0]['suggested_arguments']['status']=='CREATED'

def test_18_symbol_candidates_come_from_actual_ast():
    candidates=runtime_tools.symbol_candidates('compute_total')
    assert any(c['symbol']=='total' and c['path']=='services/pricing.py' for c in candidates)
    for c in candidates:
        assert c['symbol'] in (runtime_tools.registry.ROOT/c['path']).read_text()

def test_19_submission_retry_is_bounded():
    b=Budgets()
    for _ in range(3): b.consume('submission_retry')
    with pytest.raises(RuntimeFailure): b.consume('submission_retry')
    assert b.used['submission_retry']==3

def test_20_real_http_provider_retry_bounded(monkeypatch):
    server=local_provider(monkeypatch,[(429,{}),(500,{}),(500,{})])
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            async def retry(): s.budgets.consume('provider_retry');await persist()
            with pytest.raises(provider.ProviderError):
                await provider.complete(s.incident_id,s.run_id,'ProtocolFixture',[{'role':'user','content':'fixture'}],retry_hook=retry)
            rows=await database.query('SELECT * FROM llm_calls WHERE run_id=%s',(s.run_id,))
            assert len(rows)==3 and s.budgets.used['provider_retry']==2
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

def test_21_not_offered_cannot_runaway_or_consume_exploration(monkeypatch):
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            s.budgets.limits['correction']=2
            for i in range(2):
                result=await runtime_tools.execute(s,'execute_shell',{'command':'never'},str(i),{'read_evidence'},persist)
                assert result['error']['error_code']=='TOOL_NOT_AVAILABLE_IN_PHASE'
            with pytest.raises(RuntimeFailure):
                await runtime_tools.execute(s,'execute_shell',{},'3',{'read_evidence'},persist)
            assert s.budgets.used.get('exploration',0)==0
    asyncio.run(run())

@pytest.mark.parametrize('finish,expected',[('length','OUTPUT_TRUNCATED_CONFIRMED'),(None,'OUTPUT_TRUNCATED_SUSPECTED')])
def test_22_truncation_never_claimed_without_finish_reason(monkeypatch,finish,expected):
    server=local_provider(monkeypatch,[(200,provider_payload(finish))])
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            response=await provider.complete(s.incident_id,s.run_id,'ProtocolFixture',[{'role':'user','content':'fixture'}],include_metadata=True)
            assert response['_runtime']['truncation']==expected
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

def test_23_fsm_and_tool_error_persist_and_receipt_replay(monkeypatch):
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            # Actual Redis observation; generated IDs belong to this run.
            observed=await runtime_tools.execute(s,'inspect_redis',{},'observe',runtime_tools.NAMES,persist)
            payload=hypothesis();payload['evidence_ids']=observed['evidence_ids'];payload['status']='UPDATED'
            invalid=await runtime_tools.execute(s,'record_hypothesis',payload,'invalid',runtime_tools.NAMES,persist)
            assert invalid['error']['error_code']=='STATE_TRANSITION_INVALID'
            restored=InvestigationState.model_validate((await checkpoints.load(s.run_id))['payload'])
            assert restored.validation_errors['record_hypothesis']['expected']=={'allowed':['CREATED']}
            payload['status']='CREATED'
            result=await runtime_tools.execute(s,'record_hypothesis',payload,'created',runtime_tools.NAMES,persist)
            assert not result.get('error')
            again=await runtime_tools.execute(s,'record_hypothesis',payload,'created',runtime_tools.NAMES,persist)
            assert again==result
            rows=await database.query("SELECT * FROM tool_calls WHERE run_id=%s AND external_id='created'",(s.run_id,))
            assert len(rows)==1 and not s.validation_errors and s.critical_evidence
            record=await database.query('SELECT status FROM hypotheses WHERE run_id=%s',(s.run_id,),one=True)
            assert record['status']=='CREATED'
    asyncio.run(run())

def test_24_truth_paths_inaccessible_and_no_runtime_truth_import():
    for path in ('sentinel/scenarios.py','sentinel/evaluator.py','evaluation/baselines/rule.json','.env','services/app.py'):
        with pytest.raises(ValueError): runtime_tools.registry.read_source(path)
    for filename in ('runtime_state.py','runtime_tools.py','runtime_agent.py','structured_output.py'):
        tree=ast.parse(Path('/app/sentinel',filename).read_text())
        assert not any(isinstance(n,ast.ImportFrom) and any(x in (n.module or '') for x in ('scenarios','evaluator')) for n in ast.walk(tree))

def test_25_secrets_absent_context(monkeypatch):
    from sentinel import security
    monkeypatch.setattr(security,'settings',lambda:{'LLM_API_KEY':'synthetic-context-secret'})
    s=state();s.data['signal']={'log':'synthetic-context-secret','authorization':'Bearer private'}
    s.pin_error('test',ToolError(error_code='TEST',message='synthetic-context-secret'))
    text=json.dumps(s.rebuild({}))
    assert 'synthetic-context-secret' not in text and 'Bearer private' not in text

def test_26_pinned_overflow_fails_explicitly_instead_of_slicing():
    s=state();s.critical_evidence[E1]={'needed':'x'*5000}
    with pytest.raises(RuntimeFailure,match='PINNED_CONTEXT_OVERFLOW'): s.rebuild({},1000)

def test_27_rejected_hypothesis_cannot_be_silently_reopened():
    s=state();s.apply_hypothesis(hypothesis());s.apply_hypothesis(hypothesis('REJECTED'))
    assert not s.active_hypotheses
    with pytest.raises(RuntimeFailure): s.apply_hypothesis(hypothesis('UPDATED'))

def test_28_real_source_read_preserves_numbered_tail(monkeypatch):
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            result=await runtime_tools.execute(s,'read_source_file',{'path':'services/pricing.py'},'code',runtime_tools.NAMES,persist)
            assert result['result']['source'].endswith('return round(price * quantity * (1 - discount), 2)')
            # Tool execution alone cannot prove model delivery. Only the actual
            # message context grants the citation (regression for dropped P2 data).
            assert not any(r.get('path')=='services/pricing.py' for r in s.read_registry.values())
            from sentinel.context_delivery import visible_reads
            shown={'P2':[{'tool':'read_source_file','output':result}]}
            s.read_registry.update(visible_reads(shown,'provider-fixture'))
            assert any(r.get('path')=='services/pricing.py' for r in s.read_registry.values())
    asyncio.run(run())

def test_29_json_string_arguments_trip_real_breaker(monkeypatch):
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            raw=json.dumps({'path':'services/pricing.py','symbol':'absent_symbol'})
            for attempt in range(2):
                result=await runtime_tools.execute(s,'get_code_symbol',raw,str(attempt),runtime_tools.NAMES,persist)
                assert result['error']['error_code']=='SYMBOL_NOT_FOUND'
            result=await runtime_tools.execute(s,'get_code_symbol',raw,'third',runtime_tools.NAMES,persist)
            assert result['error']['error_code']=='CIRCUIT_BREAKER'
            result=await runtime_tools.execute(s,'get_code_symbol',{'path':'services/pricing.py','symbol':'total'},'changed',runtime_tools.NAMES,persist)
            assert not result.get('error') and not s.validation_errors
    asyncio.run(run())

def test_30_receipt_restores_budget_after_commit_before_checkpoint(monkeypatch):
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            await persist()
            async def lost_checkpoint(): pass
            result=await runtime_tools.execute(s,'inspect_redis','{}','crash-boundary',runtime_tools.NAMES,lost_checkpoint)
            loaded=InvestigationState.model_validate((await checkpoints.load(s.run_id))['payload'])
            assert not loaded.budgets.used
            async def save_loaded(): await checkpoints.save(loaded.incident_id,loaded.run_id,loaded.phase,loaded.model_dump())
            replay=await runtime_tools.execute(loaded,'inspect_redis','{}','crash-boundary',runtime_tools.NAMES,save_loaded)
            assert replay==result and loaded.budgets.used=={'exploration':1} and loaded.tool_calls==1
            await runtime_tools.execute(loaded,'inspect_redis','{}','crash-boundary',runtime_tools.NAMES,save_loaded)
            assert loaded.tool_calls==1 and loaded.budgets.used=={'exploration':1}
    asyncio.run(run())

def test_31_malformed_json_error_receipt_can_resume(monkeypatch):
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            result=await runtime_tools.execute(s,'inspect_redis','{','bad-json',runtime_tools.NAMES,persist)
            assert result['error']['error_code']=='INVALID_ARGUMENT_JSON'
            loaded=InvestigationState.model_validate((await checkpoints.load(s.run_id))['payload'])
            replay=await runtime_tools.execute(loaded,'inspect_redis','{','bad-json',runtime_tools.NAMES,persist)
            assert replay==result and loaded.validation_errors['inspect_redis']['message']
    asyncio.run(run())
