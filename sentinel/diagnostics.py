"""Operator projection of durable state; excludes request envelopes and model reasoning internals."""
from .security import serial

def project(checkpoint,measurements,provider_calls,events):
    state=(checkpoint or {}).get('payload') or {}
    limits=state.get('budgets',{}).get('limits',{})
    used=state.get('budgets',{}).get('used',{})
    return serial({'source':'MEASURED_RUNTIME_STATE','checkpoint':{k:(checkpoint or {}).get(k) for k in ('phase','updated_at')},
        'runtime_version':state.get('version'),'round':state.get('round'),'tool_calls':state.get('tool_calls'),
        'resume_count':state.get('resume_count'),'convergence':state.get('convergence'),
        'budgets':[{'name':key,'used':used.get(key,0),'limit':limit,'remaining':max(0,limit-used.get(key,0))} for key,limit in limits.items()],
        'pinned_errors':state.get('validation_errors',{}),'missing_requirements':state.get('missing_requirements',[]),
        'active_hypotheses':state.get('active_hypotheses',{}),'critical_evidence_ids':list(state.get('critical_evidence',{})),
        'unfinished_tools':[a.get('function',{}).get('name') for a in state.get('unfinished_actions',[])],
        'read_registry_count':len(state.get('read_registry',{})),'last_error':state.get('data',{}).get('last_error'),
        'context_measurements':measurements,'provider_calls':provider_calls,'event_counts':events,
        'legacy_state_unavailable':not bool(limits),
        'measurement_note':'Provider tokens are reported usage. Character sizes are measured representations; characters/4 token sizes are estimates. Compression is not evidence of diagnosis accuracy.'})
