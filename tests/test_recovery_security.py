"""Actual boundary failures and durable restore; not model reasoning accuracy."""
import asyncio
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import sys
import threading
import time
import uuid
import httpx
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from test_runtime_reliability import real_run
from sentinel import checkpoints,runtime_tools
from sentinel.runtime_agent import Runner
from sentinel.runtime_state import InvestigationState,RuntimeFailure
from sentinel.tool_registry import execute_tool
from sentinel.generic_patching import source_to_diff
from services.runtime import query

def test_conflicting_submission_retains_bounded_detail_capabilities():
    from sentinel.convergence import decide
    from sentinel.runtime_state import ToolError,offered_names
    state=InvestigationState(run_id='fixture',incident_id='fixture',round=9,convergence='SOFT_CONVERGENCE')
    state.active_hypotheses={'H1':{'status':'CREATED'}}
    state.pin_error('submit_root_cause_decision',ToolError(error_code='UNRESOLVED_CONTRADICTION',message='Fixture',
        suggested_action={'required_tool':'read_evidence','alternative_tools':['read_source_file','get_code_symbol','submit_root_cause_decision']}))
    control=decide(state,offered_names(state,runtime_tools.NAMES))
    assert control.phase=='CORRECTING' and control.required_tool is None
    assert {'read_evidence','get_code_symbol','read_source_file','submit_root_cause_decision'}<=control.allowed
    assert 'search_logs' not in control.allowed
    assert state.budgets.limits['submission_retry']==3

def test_checkout_caller_is_readable_but_fault_registry_is_not():
    from sentinel.hybrid_tools import code_symbol
    source=code_symbol('services/checkout.py','checkout')
    assert source['path']=='services/checkout.py' and 'pricing' in json.dumps(source)
    with pytest.raises(ValueError): code_symbol('services/app.py','checkout')
    with pytest.raises(ValueError): code_symbol('sentinel/scenarios.py','checkout')

@pytest.mark.parametrize('name,args',[('inspect_database',{}),('read_source_file',{'path':'services/payment.py'})])
def test_receipt_id_cannot_be_rebound_to_other_capability_or_arguments(monkeypatch,name,args):
    async def run():
        async with real_run(monkeypatch) as (state,persist):
            await runtime_tools.execute(state,'read_source_file',{'path':'services/pricing.py'},'durable-read',runtime_tools.NAMES,persist)
            count=state.tool_calls;budgets=state.budgets.model_dump()
            with pytest.raises(RuntimeFailure) as caught:
                await runtime_tools.execute(state,name,args,'durable-read',runtime_tools.NAMES,persist)
            assert caught.value.error.error_code=='TOOL_RECEIPT_MISMATCH'
            assert state.tool_calls==count and state.budgets.model_dump()==budgets
    asyncio.run(run())

def test_real_tool_timeout_survives_checkpoint_and_corrected_read_succeeds(monkeypatch):
    class Slow(BaseHTTPRequestHandler):
        def do_GET(self):
            time.sleep(.15)
            self.send_response(200);self.end_headers()
        def log_message(self,*args): pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Slow)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    original=runtime_tools.registry.invoke
    async def delayed(*args):
        async with httpx.AsyncClient(timeout=1) as client:
            return await asyncio.wait_for(client.get(f'http://127.0.0.1:{server.server_port}'),.02)
    async def run():
        async with real_run(monkeypatch) as (state,persist):
            monkeypatch.setattr(runtime_tools.registry,'invoke',delayed)
            args={'path':'services/pricing.py'}
            failed=await runtime_tools.execute(state,'read_source_file',args,'timeout-boundary',runtime_tools.NAMES,persist)
            assert failed['error']['error_code']=='TOOL_TIMEOUT'
            restored=InvestigationState.model_validate((await checkpoints.load(state.run_id))['payload'])
            assert restored.validation_errors['read_source_file']['error_code']=='TOOL_TIMEOUT'
            monkeypatch.setattr(runtime_tools.registry,'invoke',original)
            result=await runtime_tools.execute(restored,'read_source_file',args,'timeout-correction',runtime_tools.NAMES,Runner(restored).save)
            assert result['result']['path']=='services/pricing.py' and not restored.validation_errors
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

def test_actual_patch_failure_restored_and_same_attempt_replayed_before_correction(monkeypatch):
    async def run():
        async with real_run(monkeypatch) as (state,persist):
            bad='def choose_item(items):\n    return items[1]\n'
            args={'path':'services/order.py','diff':source_to_diff('services/order.py',bad)}
            result=await execute_tool('validate_generic_patch',args,state.incident_id,state.run_id,'TestAgent','patch-boundary-0')
            assert result['result']['status']=='TESTS_FAILED' and result['result']['candidate_test']['exit_code']!=0
            assert result['result']['origin']=='TEST_FIXTURE'
            state.data['patch_test_failure']=result;await persist()
            restored=InvestigationState.model_validate((await checkpoints.load(state.run_id))['payload'])
            assert restored.data['patch_test_failure']==result
            repeated=await execute_tool('validate_generic_patch',args,state.incident_id,state.run_id,'TestAgent','patch-boundary-0')
            assert repeated['tool_call_id']==result['tool_call_id']
            good='def choose_item(items):\n    if not items: raise ValueError("empty catalog")\n    return items[0]\n'
            fixed=await execute_tool('validate_generic_patch',{'path':'services/order.py','diff':source_to_diff('services/order.py',good)},state.incident_id,state.run_id,'TestAgent','patch-boundary-1')
            assert fixed['result']['candidate_verified']
            rows=await query('SELECT artifact FROM ai_patches WHERE run_id=%s',(state.run_id,))
            assert len(rows)==2 and rows[0]['artifact']['production_applied'] is False
    asyncio.run(run())

@pytest.mark.parametrize('name,args',[
    ('read_source_file',{'path':'../../.env'}),
    ('read_source_file',{'path':'/run/sentinel/provider.env'}),
    ('read_source_file',{'path':'sentinel/evaluator.py'}),
    ('read_source_file',{'path':'sentinel/scenarios.py'}),
    ('read_source_file',{'path':'services/pricing.py; touch /work/PWNED'}),
    ('search_logs',{'service':"inventory-service'; DROP TABLE incidents;--"}),
    ('inspect_database',{'sql':'DROP TABLE incidents'}),
    ('shell',{'command':'cat /run/sentinel/provider.env'}),
    ('http_request',{'url':'https://example.invalid/exfil'}),
    ('validate_generic_patch',{'path':'services/order.py','diff':'malicious'}),
    ('search_repository',{'text':'x'*21000}),
])
def test_runtime_security_denies_adversarial_capability_arguments(monkeypatch,name,args):
    async def run():
        async with real_run(monkeypatch) as (state,persist):
            try: result=await runtime_tools.execute(state,name,args,'attack',runtime_tools.NAMES,persist)
            except RuntimeFailure as exc: result={'error':exc.public()}
            assert result.get('error')
            assert await query('SELECT id FROM incidents WHERE id=%s',(state.incident_id,),one=True)
            assert not Path('/work/PWNED').exists()
    asyncio.run(run())

def test_background_worker_recovers_from_actual_kafka_bootstrap_failure():
    from aiokafka import AIOKafkaConsumer
    from services.background import supervise
    import os
    async def run():
        state={};attempts=0;ready=asyncio.Event()
        def factory():
            nonlocal attempts
            attempts+=1
            return AIOKafkaConsumer(bootstrap_servers='127.0.0.1:1' if attempts==1 else os.environ['KAFKA_BOOTSTRAP'],request_timeout_ms=1000)
        async def process(consumer):
            assert state['ready'] and await consumer.topics()
            ready.set();await asyncio.Future()
        task=asyncio.create_task(supervise(factory,process,state,initial_delay=.01))
        try:
            await asyncio.wait_for(ready.wait(),15)
            assert attempts==2 and state['restarts']==1 and state['ready']
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError): await task
        assert not state['ready']
    asyncio.run(run())
