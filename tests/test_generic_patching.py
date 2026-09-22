"""Candidate safety and actual scoped dependencies; fixture code is NOT AI output."""
import asyncio
import difflib
import json
from pathlib import Path
import uuid
import pytest
from sentinel.generic_patching import ROOT,PROFILES,allowed_path,validate_source,parse_diff,risk,validate_candidate,source_to_diff
from sentinel.remediation import enforce_eligibility
from sentinel.runtime_tools import NAMES

def diff(path,source):
    return ''.join(difflib.unified_diff((ROOT/path).read_text().splitlines(True),source.splitlines(True),fromfile='a/'+path,tofile='b/'+path))

@pytest.mark.parametrize('path',['.env','../services/pricing.py','services/../pricing.py','services\\pricing.py','evaluation/benchmarks/x','sentinel/evaluator.py','tests/domain_contract.py','compose.yaml'])
def test_protected_and_traversal_paths_rejected(path):
    with pytest.raises(ValueError): allowed_path(path)

@pytest.mark.parametrize('body',[
    "import os\ndef normalize_amount(amount): return amount\n",
    "def normalize_amount(amount): return amount.__class__\n",
    "def normalize_amount(amount): return open('.env').read()\n",
    "def normalize_amount(amount): return eval('1')\n",
    "def normalize_amount(amount):\n    while True: pass\n",
    "def normalize_amount(amount): return normalize_amount(amount)\n",
    "def normalize_amount(amount): return globals()\n",
    "def normalize_amount(amount): return __builtins__\n",
    "def normalize_amount(amount, extra=0): return amount\n",
    "def normalize_amount(amount): return amount\nprint('side effect')\n",
])
def test_malicious_or_signature_breaking_candidates_rejected(body):
    with pytest.raises(ValueError): validate_source('services/payment.py',body)

def test_unified_diff_validates_base_and_rejects_other_paths():
    path='services/order.py';source='def choose_item(items):\n    if not items: raise ValueError("catalog empty")\n    return items[0]\n'
    patch=diff(path,source);assert parse_diff(patch)[3]==source
    with pytest.raises(ValueError): parse_diff(patch.replace('services/order.py','tests/domain_contract.py'))
    with pytest.raises(ValueError): parse_diff(patch.replace('return items[0]','return items[1]',1))

def test_generic_test_capability_is_never_offered_to_investigator():
    assert 'validate_generic_patch' not in NAMES

def test_source_serialization_preserves_model_logic_and_exact_hunk_counts():
    source='def normalize_amount(amount):\n    if amount is None: raise ValueError("invalid")\n    return float(amount)\n'
    patch=source_to_diff('services/payment.py',source)
    assert parse_diff(patch)[3]==source
    with pytest.raises(ValueError): source_to_diff('tests/domain_contract.py',source)

def test_unsupported_code_eligibility_fails_closed():
    decision={'category':'CODE_EXCEPTION','patch_decision':'CODE_PATCH','code_locations':[{'path':'services/runtime.py'}]}
    result=enforce_eligibility({'action':'CODE_PATCH','code_path':'services/runtime.py','rationale':'unsupported path','required_validation':[]},decision)
    assert result['action']=='NO_AUTOMATIC_REMEDIATION' and not result['automatic_execution']

@pytest.mark.parametrize('action',['CONFIG_CHANGE','INFRA_REMEDIATION','NO_AUTOMATIC_REMEDIATION'])
def test_noncode_remediation_remains_manual(action):
    result=enforce_eligibility({'action':action,'code_path':None,'rationale':'observed dependency issue','required_validation':[]},{})
    assert result['action']==action and result['automatic_execution'] is False

def test_financial_patch_is_high_risk_and_cannot_auto_apply():
    assessment=risk('--- a/services/payment.py\n+++ b/services/payment.py\n+    if amount < 0: raise ValueError("invalid")','services/payment.py')
    assert assessment['level']=='HIGH' and not assessment['automatic_apply_allowed']

def test_actual_multiservice_candidate_uses_real_isolated_dependencies():
    async def run():
        path='services/order.py'
        fixture='def choose_item(items):\n    if not items: raise ValueError("catalog empty")\n    return items[0]\n'
        artifact=await validate_candidate(diff(path,fixture),str(uuid.uuid4()),origin='TEST_FIXTURE')
        assert artifact['origin']=='TEST_FIXTURE' and artifact['candidate_verified']
        assert artifact['baseline_test']['exit_code']!=0 and artifact['candidate_test']['exit_code']==0
        old,new=artifact['replay']['before'],artifact['replay']['after']
        assert old['business_violation_pct']==100 and new['business_violation_pct']==0
        assert old['error_pct']==100 and new['error_pct']==0
        assert set(new['services'])=={'order','inventory','payment'}
        assert new['dependencies']['postgres']['rows']['orders']>=1
        assert new['dependencies']['redis']['catalog_ttl']>0
        assert new['dependencies']['kafka']['healthy_order_event_verified'] is True
        assert new['dependencies']['postgres']['schema']!=old['dependencies']['postgres']['schema']
    asyncio.run(run())
