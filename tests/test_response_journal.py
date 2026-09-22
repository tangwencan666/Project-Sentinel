"""Real HTTP/PostgreSQL resume boundaries; synthetic responses are protocol fixtures."""
import asyncio
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from test_runtime_reliability import real_run,local_provider,provider_payload,BoundaryServer
from sentinel import provider,checkpoints
from sentinel.runtime_agent import Runner
from sentinel.runtime_state import InvestigationState
from sentinel.hybrid_tools import InvestigationPlan
from services.runtime import query

def test_received_public_response_is_durably_replayed_without_another_http_request(monkeypatch):
    payload=provider_payload('stop');payload['choices'][0]['message']['reasoning_content']='PRIVATE_PROVIDER_FIELD_MUST_NOT_BE_STORED'
    server=local_provider(monkeypatch,[(200,payload)])
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            messages=[{'role':'user','content':'protocol fixture'}]
            first=await provider.complete(s.incident_id,s.run_id,'ProtocolFixture',messages,include_metadata=True,logical_request_id='durable:0')
            second=await provider.complete(s.incident_id,s.run_id,'ProtocolFixture',messages,include_metadata=True,logical_request_id='durable:0')
            assert len(BoundaryServer.requests)==1
            assert first['content']==second['content'] and first['_runtime']['call_id']==second['_runtime']['call_id']
            assert second['_runtime']['response_replayed'] is True
            rows=await query('SELECT response_payload FROM llm_calls WHERE run_id=%s',(s.run_id,))
            assert len(rows)==1 and 'PRIVATE_PROVIDER_FIELD_MUST_NOT_BE_STORED' not in json.dumps(rows)
            with pytest.raises(provider.ProviderError,match='REQUEST_REPLAY_MISMATCH'):
                await provider.complete(s.incident_id,s.run_id,'ProtocolFixture',[{'role':'user','content':'changed'}],logical_request_id='durable:0')
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

def test_structured_repair_resume_does_not_charge_or_send_the_same_repair_twice(monkeypatch):
    bad=provider_payload('stop');bad['choices'][0]['message']['content']='{'
    good=provider_payload('stop');good['choices'][0]['message']['content']=json.dumps({'suspected_services':['order-service'],'initial_hypotheses':['boundary'],'tool_priority':['read_evidence'],'stop_conditions':['enough evidence']})
    server=local_provider(monkeypatch,[(200,bad),(200,good)])
    class CrashAfterResponse(Exception): pass
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            s.version='4.1';runner=Runner(s);real_llm=runner.llm
            async def crash(agent,messages,**kwargs):
                result=await real_llm(agent,messages,**kwargs)
                if s.data['structured_jobs']['Planner']['attempt']==1: raise CrashAfterResponse()
                return result
            runner.llm=crash
            request=[{'role':'system','content':'Return JSON'},{'role':'user','content':'protocol fixture'}]
            with pytest.raises(CrashAfterResponse): await runner.structured('Planner',InvestigationPlan,request)
            saved=InvestigationState.model_validate((await checkpoints.load(s.run_id))['payload'])
            assert saved.budgets.used['schema_repair']==1
            recovered=await Runner(saved).structured('Planner',InvestigationPlan,request)
            assert recovered['suspected_services']==['order-service']
            assert saved.budgets.used['schema_repair']==1 and len(BoundaryServer.requests)==2
            assert saved.data['structured_jobs']['Planner']['attempt']==2
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

@pytest.mark.parametrize('status',[429,500])
def test_provider_failure_then_checkpoint_resume_preserves_retry_budget(monkeypatch,status):
    good=provider_payload('stop');good['choices'][0]['message']['content']='{"ok":true}'
    server=local_provider(monkeypatch,[(status,{})]*3+[(200,good)])
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            request=[{'role':'user','content':'protocol fixture'}]
            with pytest.raises(provider.ProviderError): await Runner(s).llm('ProtocolFixture',request,request_key='retry-boundary')
            restored=InvestigationState.model_validate((await checkpoints.load(s.run_id))['payload'])
            assert restored.budgets.used['provider_retry']==2
            response=await Runner(restored).llm('ProtocolFixture',request,request_key='retry-boundary')
            assert response['content']=='{"ok":true}' and restored.budgets.used['provider_retry']==2
            rows=await query('SELECT status FROM llm_calls WHERE run_id=%s',(s.run_id,))
            assert len(rows)==4 and sum(r['status']=='failed' for r in rows)==3
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()
