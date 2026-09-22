import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from field_repair import prepare,messages,apply

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
