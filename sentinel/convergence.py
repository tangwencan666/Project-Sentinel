"""Supervisor progress policy introduced in the 3.1.1 reliability follow-up."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Control:
    phase: str
    allowed: frozenset[str]
    required_tool: str | None
    reason: str

REPAIR_TOOLS={'read_evidence','read_source_file','get_code_context','get_code_symbol',
              'get_trace_detail','record_hypothesis','submit_root_cause_decision'}

def decide(state,available):
    """Keep exploration finite and reserve synthesis independently of tool appetite.

    This controls protocol progress only. The model must still supply its own
    hypothesis, evidence, uncertainty and final diagnosis; no diagnosis is inferred
    by this controller. Missing evidence may result in UNKNOWN or verifier rejection.
    """
    names=set(available)
    requirements=state.missing_requirements
    if requirements:
        required={item['required_tool'] for item in requirements} & names
        if required:
            return Control('CORRECTING',frozenset(required),next(iter(required)) if len(required)==1 else None,
                           'Complete explicit missing submission requirements; correction budget remains available.')
    # Repair one concrete failed operation before expanding the investigation.
    for name,error in state.validation_errors.items():
        if error.get('error_code') in ('CIRCUIT_BREAKER','TOOL_NOT_AVAILABLE_IN_PHASE'):
            continue  # changed arguments or another valid capability can resolve these
        required=error.get('suggested_action',{}).get('required_tool',name)
        if required in names:
            if error.get('error_code')=='UNRESOLVED_CONTRADICTION':
                corrections=({required}|set(error['suggested_action'].get('alternative_tools',[]))) & names
                return Control('CORRECTING',frozenset(corrections),None,
                    'Resolve the cited contradiction with bounded detail/code reads, or submit UNKNOWN. Broad exploration remains closed.')
            return Control('CORRECTING',frozenset({required}),required,'Resolve the pinned validation feedback.')
    exploration=state.budgets.used.get('exploration',0)
    if not state.active_hypotheses and (state.round>=3 or exploration>=8):
        return Control('HYPOTHESIS_REQUIRED',frozenset({'record_hypothesis'}),'record_hypothesis',
                       'Record a provisional hypothesis from observed evidence; uncertainty is permitted.')
    if state.active_hypotheses and (state.round>=6 or exploration>=12 or state.convergence!='NORMAL'):
        return Control('SYNTHESIS_REQUIRED',frozenset({'submit_root_cause_decision'}),'submit_root_cause_decision',
                       'Submit a bounded candidate now. The local readiness gate may request specific missing evidence; unsupported causes must remain UNKNOWN.')
    # A single failed tool cannot force an endless sequence of the same invocation.
    if state.convergence!='NORMAL':
        names &= REPAIR_TOOLS | {'inspect_database','inspect_redis','inspect_kafka','get_service_health'}
    return Control('EXPLORING',frozenset(names),None,'Collect the missing corroborating observation; do not repeat broad sweeps.')
