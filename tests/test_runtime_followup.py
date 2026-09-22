"""Follow-up reliability regressions; no paid-model calls or accuracy claims."""
import json
from pathlib import Path
import sys
import pytest
import asyncio
sys.path.insert(0,str(Path(__file__).parent))
from sentinel.convergence import decide
from sentinel.redaction_walk import redact
from sentinel.context_delivery import detail_page,visible_reads,provider_messages
from sentinel.runtime_state import InvestigationState

NAMES={'search_logs','query_metrics','get_trace','inspect_redis','inspect_database','inspect_kafka',
       'read_evidence','read_source_file','record_hypothesis','submit_root_cause_decision','get_code_symbol'}
def state(): return InvestigationState(run_id='run',incident_id='incident')

def test_repetitive_exploration_cannot_starve_hypothesis_and_submission():
    s=state()
    for turn in range(3):
        s.round=turn
        assert decide(s,NAMES).phase=='EXPLORING'
    s.round=3
    assert decide(s,NAMES).required_tool=='record_hypothesis'
    s.active_hypotheses={'H-fixture':{'status':'CREATED'}}
    for turn in range(4,6):
        s.round=turn;assert decide(s,NAMES).phase=='EXPLORING'
    s.round=6
    assert decide(s,NAMES).required_tool=='submit_root_cause_decision'

def test_unread_citation_gets_correction_even_after_completion_budget_exhausted():
    s=state();s.round=15;s.active_hypotheses={'H-fixture':{}}
    s.budgets.used['evidence_completion']=8
    s.missing_requirements=[{'required_tool':'read_source_file','suggested_arguments':{'path':'services/pricing.py'}}]
    assert decide(s,NAMES).required_tool=='read_source_file'
    s.missing_requirements=[]
    assert decide(s,NAMES).required_tool=='submit_root_cause_decision'

def test_multiple_missing_requirements_leave_all_required_tools_available():
    s=state();s.missing_requirements=[{'required_tool':'record_hypothesis'},{'required_tool':'read_evidence'}]
    control=decide(s,NAMES)
    assert control.required_tool is None and control.allowed=={'record_hypothesis','read_evidence'}

def test_protocol_forcing_does_not_construct_a_diagnosis():
    s=state();s.round=12;s.active_hypotheses={'H-fixture':{}}
    control=decide(s,NAMES)
    assert control.phase=='SYNTHESIS_REQUIRED' and not s.data.get('decision')

def test_redaction_reads_configuration_once_for_large_checkpoint():
    calls=[]
    def settings(): calls.append(1);return {'LLM_API_KEY':'test-only-secret'}
    value={'data':[{'a':'test-only-secret','b':'Authorization: Bearer token','c':'https://user:pass@example.com'} for _ in range(5000)]}
    encoded=json.dumps(redact(value,settings))
    assert len(calls)==1 and 'test-only-secret' not in encoded and 'Bearer token' not in encoded and 'user:pass' not in encoded

def test_redaction_reloads_configuration_between_calls():
    current={'LLM_API_KEY':'first-test-key'}
    assert redact('first-test-key',lambda:current)=='[REDACTED]'
    current['LLM_API_KEY']='rotated-test-key'
    assert redact('rotated-test-key',lambda:current)=='[REDACTED]'

def test_dropped_detail_does_not_grant_a_code_citation():
    s=state()
    s.recent_results=[{'tool':'read_source_file','output':{'evidence_ids':['E-code'],
        'result':{'path':'services/runtime.py','start_line':1,'end_line':150,'source':'x'*20000}}}]
    context=s.rebuild({},4000)
    assert not context['P2']
    assert 'E-code' not in visible_reads(context,'provider-fixture')

def test_shown_detail_grants_only_the_actual_range():
    context={'P2':[{'tool':'read_source_file','output':{'evidence_ids':['E-code'],
        'result':{'path':'services/pricing.py','start_line':3,'end_line':6,'source':'3: def total...'}}}]}
    read=visible_reads(context,'provider-fixture')['E-code']
    assert read['start_line']==3 and read['end_line']==6 and read['provider_call_id']=='provider-fixture'

def test_truncated_summary_does_not_grant_full_file_citation():
    context={'evidence':{'items':[{'id':'E-code','kind':'read_source_file','truncated':True,
        'observations':'{"path":"services/pricing.py","start_line":3'}]}}
    assert 'path' not in visible_reads(context,'provider-fixture')['E-code']

def test_real_frozen_trace_pages_reconstruct_every_original_span():
    # Included genuine recording, identical to the frozen V3.1 trace payload;
    # independent of ignored internal archives in a fresh checkout.
    root=Path(__file__).resolve().parents[1]
    relative='history/9052a3ec-d1ae-4486-9f44-b8330d479e82.json'
    artifact=root/'portfolio/data'/relative
    import hashlib
    manifest=json.loads((root/'portfolio/data/manifest.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(artifact.read_bytes()).hexdigest()==manifest['files'][relative]['sha256']
    row=json.loads(artifact.read_text(encoding='utf-8'))
    assert row['trial']['scenario']=='n_plus_one'
    original=next(e['payload'] for e in row['evidence'] if e['kind']=='get_trace_detail')
    assert sum(len(t['spans']) for t in original)==90
    for trace in original:
        received=[];offset=0
        while True:
            page=detail_page([trace],offset)[0]
            assert all(s in trace['spans'] for s in page['spans'])
            received.extend(page['spans']);offset=page['pagination']['next_offset']
            if offset is None: break
        assert received==trace['spans']

def test_exact_nested_json_envelope_budget_preserves_pinned_state():
    context={'P0':{'error':'must survive'},'P1':{'critical':'must survive'},
             'P2':[{'quoted_json':'\\"'*12000}],'P3':[]}
    assert len(json.dumps(context,ensure_ascii=False))<90000
    unbounded=[{'role':'system','content':'system'},{'role':'user','content':json.dumps(context)}]
    assert len(json.dumps(unbounded,ensure_ascii=False))>90000
    messages,shown=provider_messages('system',context)
    assert len(json.dumps(messages,ensure_ascii=False))<=90000
    assert shown['P0']==context['P0'] and shown['P1']==context['P1'] and not shown['P2']
    assert context['P2']  # checkpoint remains an intact raw history

def test_unfittable_pinned_envelope_fails_without_silent_loss():
    with pytest.raises(ValueError,match='PINNED_CONTEXT_OVERFLOW'):
        provider_messages('system',{'P0':{'error':'\\"'*24000}},90000)

def test_snapshot_redaction_matches_existing_security_contract(monkeypatch):
    from sentinel import security
    cfg={'LLM_API_KEY':'unit-only-key'}
    monkeypatch.setattr(security,'settings',lambda:cfg)
    values=[{'api_key':'never shown','nested':['unit-only-key','Bearer private','password=private',
        'https://user:private@example.com/path',{'ordinary':'preserved','secret':'hidden'}]},None,42,True]
    assert redact(values,lambda:cfg)==security.redact(values)

def test_parse_error_remains_on_original_call_and_checkpoint(monkeypatch):
    from test_runtime_reliability import real_run,local_provider,provider_payload
    from sentinel import provider,checkpoints
    from sentinel.structured_output import mark_parse
    from sentinel.runtime_state import ToolError
    from services.runtime import query
    server=local_provider(monkeypatch,[(200,provider_payload())])
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            response=await provider.complete(s.incident_id,s.run_id,'ProtocolFixture',[{'role':'user','content':'fixture'}],include_metadata=True)
            s.provider_state=response['_runtime']
            await mark_parse(s.provider_state,ToolError(error_code='INVALID_ARGUMENT_JSON',message='unterminated JSON'))
            await mark_parse(s.provider_state)  # a valid sibling must not erase the original failure
            await persist()
            stored=await query('SELECT diagnostics FROM llm_calls WHERE id=%s',(s.provider_state['call_id'],),one=True)
            restored=(await checkpoints.load(s.run_id))['payload']['provider_state']
            assert stored['diagnostics']['parse_status']==restored['parse_status']=='invalid'
            assert restored['parse_error']['error_code']=='INVALID_ARGUMENT_JSON'
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

def test_supervisor_forced_tool_reaches_actual_http_request(monkeypatch):
    from test_runtime_reliability import real_run,local_provider,provider_payload,BoundaryServer
    from sentinel.runtime_agent import Runner
    from sentinel.runtime_tools import tools_for
    server=local_provider(monkeypatch,[(200,provider_payload('stop'))])
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            s.round=3;control=decide(s,NAMES)
            choice={'type':'function','function':{'name':control.required_tool}}
            await Runner(s).llm('ProtocolFixture',[{'role':'user','content':'fixture'}],tools_for(control.allowed),choice)
            assert BoundaryServer.requests[0]['tool_choice']==choice
            assert choice['function']['name']=='record_hypothesis'
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

def test_protocol_fixture_usage_is_excluded_from_global_provider_totals(monkeypatch):
    from test_runtime_reliability import real_run,local_provider,provider_payload
    from sentinel import provider
    from sentinel.storage import usage
    server=local_provider(monkeypatch,[(200,provider_payload('stop'))])
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            await provider.complete(s.incident_id,s.run_id,'ProtocolFixture',[{'role':'user','content':'fixture'}])
            detail=await usage(s.incident_id);global_usage=await usage()
            assert len(detail['calls'])==1
            assert not any(c['run_id']==s.run_id for c in global_usage['calls'])
    try: asyncio.run(run())
    finally: server.shutdown();server.server_close()

def compact_decision():
    from test_runtime_reliability import E1,E2
    return dict(hypothesis='Observed protocol fixture',affected_service='order-service',
        root_cause='Protocol contract test, not a diagnosis.',category='UNKNOWN',evidence_ids=[E1,E2],
        code_locations=[],reasoning_summary='Uncertain.',recommended_fix='Investigate.',remaining_uncertainty=['Not graded.'],
        patch_decision='NO_CODE_PATCH',supporting_evidence=[E1,E2],contradicting_evidence=[],
        deterministic_signals=[],llm_findings=[])

def test_root_contract_bounds_repeated_prose_and_signal_ids():
    from sentinel.submission_contract import CompactRootCauseDecision
    from pydantic import ValidationError
    value=compact_decision()
    assert CompactRootCauseDecision.model_validate(value).category=='UNKNOWN'
    value['root_cause']='x'*551
    with pytest.raises(ValidationError): CompactRootCauseDecision.model_validate(value)
    value=compact_decision();value['deterministic_signals']=[dict(signal_id='invented.pool_pressure',disposition='refuted',evidence_ids=[],explanation='invented')]
    with pytest.raises(ValidationError): CompactRootCauseDecision.model_validate(value)

def test_dynamic_submission_schema_exposes_only_observed_signals():
    from test_runtime_reliability import state
    from sentinel.runtime_tools import tools_for
    s=state();s.data['triage']={'signals':[{'signal_id':'S2'}]}
    schema=tools_for({'submit_root_cause_decision'},s)[0]['function']['parameters']
    assert schema['properties']['deterministic_signals']['maxItems']==1
    assert schema['$defs']['CompactSignalAssessment']['properties']['signal_id']['enum']==['S2']
    s.data['triage']['signals']=[]
    schema=tools_for({'submit_root_cause_decision'},s)[0]['function']['parameters']
    assert schema['properties']['deterministic_signals']['maxItems']==0

def test_unobserved_signal_rejected_before_submission_execution(monkeypatch):
    from test_runtime_reliability import real_run
    from sentinel import runtime_tools
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            value=compact_decision()
            value['deterministic_signals']=[dict(signal_id='S99',disposition='uncertain',evidence_ids=[],explanation='not observed')]
            result=await runtime_tools.execute(s,'submit_root_cause_decision',value,'invalid-signal',{'submit_root_cause_decision'},persist)
            assert result['error']['error_code']=='SCHEMA_VALIDATION_FAILED'
            assert result['error']['expected']==[] and 'decision' not in s.data
    asyncio.run(run())

def test_truncation_repair_sees_confirmed_finish_reason():
    from test_runtime_reliability import state,PLAN
    from sentinel.structured_output import structured
    from sentinel.hybrid_tools import InvestigationPlan
    async def run():
        s=state();seen=[]
        async def invoke(messages):
            seen.append(messages)
            return {'content':'{"suspected_services":' if len(seen)==1 else json.dumps(PLAN),
                    '_runtime':{'finish_reason':'length' if len(seen)==1 else 'stop'}}
        async def persist(): pass
        async def record(*args): pass
        await structured([{'role':'system','content':'Return JSON'},{'role':'user','content':'protocol fixture'}],InvestigationPlan,invoke,s,'Planner',persist,record)
        feedback=json.loads(seen[1][1]['content'])
        assert feedback['finish_reason']=='length' and 'shorter' in feedback['instruction']
        assert s.budgets.used['schema_repair']==1
    asyncio.run(run())

def test_compact_contract_preserves_causal_field_semantics():
    from sentinel.submission_contract import CompactRootCauseDecision
    from sentinel.hybrid_tools import RootCauseDecision
    for name in ('supporting_evidence','contradicting_evidence'):
        assert CompactRootCauseDecision.model_fields[name].description==RootCauseDecision.model_fields[name].description
    assert 'Ruled-out alternative' in CompactRootCauseDecision.model_fields['contradicting_evidence'].description

def test_root_schema_rejections_keep_all_submission_slots(monkeypatch):
    from test_runtime_reliability import real_run
    from sentinel import runtime_tools
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            for number in range(4):
                value=compact_decision();value['hypothesis']='x'*(241+number)
                result=await runtime_tools.execute(s,'submit_root_cause_decision',value,'schema-'+str(number),{'submit_root_cause_decision'},persist)
                assert result['error']['error_code']=='FIELD_TOO_LONG'
            assert s.budgets.used=={'correction':4}
    asyncio.run(run())

def test_readiness_failure_uses_correction_not_submission(monkeypatch):
    from test_runtime_reliability import real_run
    from sentinel import runtime_tools
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            result=await runtime_tools.execute(s,'submit_root_cause_decision',compact_decision(),'not-ready',{'submit_root_cause_decision'},persist)
            assert result['error']['error_code']=='HYPOTHESIS_NOT_CREATED'
            assert s.budgets.used=={'correction':1}
    asyncio.run(run())

def test_exhausted_correction_retains_original_schema_failure(monkeypatch):
    from test_runtime_reliability import real_run
    from sentinel import runtime_tools
    from sentinel.runtime_state import RuntimeFailure
    async def run():
        async with real_run(monkeypatch) as (s,persist):
            s.budgets.used['correction']=s.budgets.limits['correction']
            value=compact_decision();value['hypothesis']='x'*241
            with pytest.raises(RuntimeFailure) as exhausted:
                await runtime_tools.execute(s,'submit_root_cause_decision',value,'exhausted',{'submit_root_cause_decision'},persist)
            assert exhausted.value.error.error_code=='BUDGET_EXHAUSTED'
            assert exhausted.value.error.actual['underlying_error']['error_code']=='FIELD_TOO_LONG'
    asyncio.run(run())
