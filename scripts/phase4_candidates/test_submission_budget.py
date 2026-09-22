"""Offline replay of retained protocol failures, never RCA success data."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).parent))
from budget_accounting import result_bucket
from sentinel.runtime_state import InvestigationState,ToolError
from sentinel.submission_contract import CompactRootCauseDecision
from sentinel.contracts import validate_diagnosis,Diagnosis
from sentinel.structured_output import parse_validate
from sentinel.runtime_state import RuntimeFailure

def test_actual_pool_failure_schema_errors_do_not_exhaust_submission():
    suite=json.loads(Path('/app/evaluation/phase4/v3.1.2-qualification.continued-1.json').read_text())
    row=next(r for r in suite['results'] if r['scenario']=='pool_exhaustion')
    calls=[t for t in row['ledger']['tool_calls'] if t['tool_name']=='submit_root_cause_decision']
    s=InvestigationState(run_id='offline',incident_id='offline')
    for call in calls[:-1]:
        bucket=result_bucket(s,call['tool_name'],ToolError(**call['error']))
        s.budgets.consume(bucket)
    assert s.budgets.used=={'correction':1,'submission_retry':2}
    value=calls[-1]['arguments']
    with pytest.raises(RuntimeFailure) as original:
        parse_validate(value,CompactRootCauseDecision)
    assert original.value.error.error_code=='FIELD_TOO_LONG'
    s.budgets.consume(result_bucket(s,calls[-1]['tool_name'],original.value.error))
    assert s.budgets.used=={'correction':2,'submission_retry':2}
    validate_diagnosis({k:v for k,v in value.items() if k in Diagnosis.model_fields},row['ledger']['evidence'])
    assert not value['contradicting_evidence']
    # A corrected future response still has one semantic submission slot. Whether
    # the model actually supplies it must be tested, never inferred as success.
    assert s.budgets.limits['submission_retry']-s.budgets.used['submission_retry']==1
    assert row['workflow_completed'] is False  # historical result stays failed
