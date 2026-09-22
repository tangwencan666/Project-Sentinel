"""Parse/schema and local readiness failures are not semantic submission attempts."""
LOCAL_REJECTIONS={'INVALID_ARGUMENT_JSON','SCHEMA_VALIDATION_FAILED','FIELD_TOO_LONG',
                  'HYPOTHESIS_NOT_CREATED','UNREAD_EVIDENCE','UNREAD_CITATION',
                  'INVALID_SERVICE','UNRESOLVED_VALIDATION','TOOL_NOT_AVAILABLE_IN_PHASE','CIRCUIT_BREAKER'}

def result_bucket(state,name,error):
    from sentinel.runtime_state import action_bucket
    if error and error.error_code in LOCAL_REJECTIONS: return 'correction'
    if name=='submit_root_cause_decision': return 'submission_retry'
    if error: return 'correction'
    return action_bucket(state,name)
