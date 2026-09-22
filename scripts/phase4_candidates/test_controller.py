"""Isolated candidate regression tests. No paid-model calls or accuracy claims."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from convergence import decide
from redaction import redact
from context_reads import detail_page,visible_reads,provider_messages
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
    artifact=Path('/evidence/results/v3.1-first-controlled.json')
    if not artifact.exists(): pytest.skip('Retained real-trace artifact mount is required for this integration regression')
    suite=json.loads(artifact.read_text())
    row=next(r for r in suite['results'] if r['scenario']=='n_plus_one')
    original=next(e['payload'] for e in row['ledger']['evidence'] if e['kind']=='get_trace_detail')
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
