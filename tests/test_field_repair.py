import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from sentinel.field_repair import prepare,messages,apply

def fixture():
    base={'root_cause':'observed cause '*80,'remaining_uncertainty':['unknown '*20],
          'evidence_ids':['E-0123456789abcdef'],'category':'UNKNOWN'}
    error={'error_code':'FIELD_TOO_LONG','expected':[
        {'type':'string_too_long','loc':['root_cause'],'ctx':{'max_length':550}},
        {'type':'string_too_long','loc':['remaining_uncertainty',0],'ctx':{'max_length':120}}]}
    return base,prepare(base,error)

def test_only_requested_fields_change_and_original_is_intact():
    base,job=fixture()
    result=apply({'replacements':[{'path':['root_cause'],'value':'An unconfirmed observed cause.'},
                                  {'path':['remaining_uncertainty',0],'value':'Still uncertain.'}]},job)
    assert result['evidence_ids']==base['evidence_ids'] and result['category']==base['category']
    assert len(base['root_cause'])>550 and len(result['root_cause'])<550
    assert json.loads(messages(job)[1]['content'])['fields'][0]['target_characters']==275

@pytest.mark.parametrize('reply',[
    {'replacements':[{'path':['evidence_ids',0],'value':'invented'}]},
    {'replacements':[{'path':['root_cause'],'value':'a'},{'path':['root_cause'],'value':'b'}]},
    {'replacements':[]}, {'root_cause':'changed'},
    {'replacements':[{'path':['root_cause'],'value':'x'*551}]},
    {'replacements':[{'path':['root_cause'],'value':42}]},
    {'replacements':[{'path':['root_cause'],'value':'ok','extra':True}]}
])
def test_unrequested_duplicate_missing_oversized_or_malformed_replacements_rejected(reply):
    _,job=fixture()
    with pytest.raises(ValueError): apply(reply,job)

def test_non_length_errors_do_not_use_field_repair():
    assert prepare('{',{'error_code':'INVALID_ARGUMENT_JSON'}) is None

def structured_fixture(outputs,crash_after_prepare=False):
    import asyncio
    from pydantic import Field
    from sentinel.contracts import Strict
    from sentinel.runtime_state import InvestigationState
    from sentinel.structured_output import structured
    class Output(Strict):
        text:str=Field(max_length=20)
        evidence_ids:list[str]
    async def run():
        state=InvestigationState(run_id='test',incident_id='test');seen=[];saved=[];crashed=False
        async def invoke(messages):
            seen.append(messages);return {'content':outputs[len(seen)-1]}
        async def persist():
            nonlocal crashed
            saved.append(state.model_dump_json())
            if crash_after_prepare and not crashed and state.data.get('structured_jobs',{}).get('Boundary',{}).get('field_repair'):
                crashed=True;raise InterruptedError('before repair dispatch')
        async def record(*args): pass
        request=[{'role':'system','content':'Return JSON'},{'role':'user','content':'protocol fixture'}]
        try: result=await structured(request,Output,invoke,state,'Boundary',persist,record)
        except InterruptedError:
            state=InvestigationState.model_validate_json(saved[-1])
            result=await structured(request,Output,invoke,state,'Boundary',persist,record)
        return result,state,seen
    return asyncio.run(run())

def test_structured_repair_uses_only_short_fields_and_preserves_citations():
    result,state,seen=structured_fixture([
        json.dumps({'text':'x'*50,'evidence_ids':['observed-id']}),
        json.dumps({'replacements':[{'path':['text'],'value':'Short observation.'}]})])
    assert result=={'text':'Short observation.','evidence_ids':['observed-id']}
    assert state.budgets.used=={'schema_repair':1} and len(seen)==2

def test_field_job_survives_checkpoint_before_dispatch():
    result,state,seen=structured_fixture([
        json.dumps({'text':'x'*50,'evidence_ids':['observed-id']}),
        json.dumps({'replacements':[{'path':['text'],'value':'Still uncertain.'}]})],crash_after_prepare=True)
    assert result['evidence_ids']==['observed-id'] and state.budgets.used=={'schema_repair':1}
    assert len(seen)==2

def test_field_repair_still_stops_after_two_invalid_responses():
    from sentinel.runtime_state import RuntimeFailure
    with pytest.raises(RuntimeFailure):
        structured_fixture([json.dumps({'text':'x'*50,'evidence_ids':[]}),'{"replacements":[]}','{"replacements":[]}'])
