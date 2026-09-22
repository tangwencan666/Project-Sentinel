"""Versioned investigation control state; observations are never control instructions."""
import hashlib
import json
from typing import Any, Literal
from pydantic import Field
from .contracts import Strict, Hypothesis
from .security import serial

SERVICES = {'gateway', 'user-service', 'order-service', 'payment-service', 'inventory-service', 'notification-service'}

class ToolError(Strict):
    error_code: str
    message: str
    retryable: bool = True
    invalid_fields: list[str] = Field(default_factory=list)
    expected: Any = None
    actual: Any = None
    suggested_action: dict = Field(default_factory=dict)

class RuntimeFailure(RuntimeError):
    def __init__(self, error: ToolError):
        self.error = error
        super().__init__(error.error_code)
    def public(self):
        return self.error.model_dump()

class RuntimeHypothesis(Hypothesis):
    status: Literal['CREATED', 'UPDATED', 'SUPPORTED', 'REJECTED', 'CONFIRMED']

TRANSITIONS = {'NONE': ['CREATED'], 'CREATED': ['UPDATED', 'SUPPORTED', 'REJECTED', 'CONFIRMED'],
               'UPDATED': ['UPDATED', 'SUPPORTED', 'REJECTED', 'CONFIRMED'],
               'SUPPORTED': ['UPDATED', 'SUPPORTED', 'REJECTED', 'CONFIRMED'],
               'REJECTED': [], 'CONFIRMED': []}

def transition(previous, target):
    allowed = TRANSITIONS.get(previous, [])
    if target not in allowed:
        raise RuntimeFailure(ToolError(error_code='STATE_TRANSITION_INVALID',
            message='Hypothesis transition rejected; create before updating.', invalid_fields=['status'],
            expected={'allowed': allowed}, actual={'from': previous, 'to': target},
            suggested_action={'required_tool': 'record_hypothesis', 'allowed': allowed}))

class Budgets(Strict):
    limits: dict[str, int] = Field(default_factory=lambda: {'exploration':28, 'evidence_completion':8,
        'correction':12, 'submission_retry':3, 'schema_repair':12, 'provider_retry':10})
    used: dict[str, int] = Field(default_factory=dict)
    def consume(self, bucket):
        if self.used.get(bucket, 0) >= self.limits[bucket]:
            raise RuntimeFailure(ToolError(error_code='BUDGET_EXHAUSTED', retryable=False,
                message=f'{bucket} budget exhausted', expected=self.limits[bucket], actual=self.used.get(bucket, 0),
                suggested_action={'stop':True, 'budget':bucket}))
        self.used[bucket] = self.used.get(bucket, 0) + 1

class InvestigationState(Strict):
    version: str = '3.1'
    run_id: str
    incident_id: str
    phase: str = 'CREATED'
    round: int = 0
    exploration_rounds: int = 0
    tool_calls: int = 0
    active_hypotheses: dict[str, dict] = Field(default_factory=dict)
    rejected_hypotheses: dict[str, dict] = Field(default_factory=dict)
    critical_evidence: dict[str, dict] = Field(default_factory=dict)
    validation_errors: dict[str, dict] = Field(default_factory=dict)
    missing_requirements: list[dict] = Field(default_factory=list)
    unfinished_actions: list[dict] = Field(default_factory=list)
    last_successful_action: dict | None = None
    budgets: Budgets = Field(default_factory=Budgets)
    provider_state: dict = Field(default_factory=dict)
    read_registry: dict[str, dict] = Field(default_factory=dict)
    recent_results: list[dict] = Field(default_factory=list)
    history: list[dict] = Field(default_factory=list)
    failure_streak: dict = Field(default_factory=dict)
    convergence: str = 'NORMAL'
    suspected_services: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    resume_count: int = 0

    def pin_error(self, name, error):
        self.validation_errors[name] = serial(error.model_dump() if isinstance(error, ToolError) else error)

    def resolve(self, name):
        self.validation_errors.pop(name, None)
        self.missing_requirements=[r for r in self.missing_requirements if r.get('required_tool')!=name]
        for key, error in list(self.validation_errors.items()):
            if error.get('suggested_action', {}).get('required_tool') == name:
                self.validation_errors.pop(key)
            elif error.get('error_code') in ('TOOL_NOT_AVAILABLE_IN_PHASE','CIRCUIT_BREAKER'):
                self.validation_errors.pop(key)
            elif name in ('read_source_file','get_code_context','get_code_symbol') and key in ('read_source_file','get_code_context','get_code_symbol','search_repository'):
                self.validation_errors.pop(key)

    def apply_hypothesis(self, value):
        hid = value['hypothesis_id']
        previous = self.active_hypotheses.get(hid) or self.rejected_hypotheses.get(hid)
        transition(previous['status'] if previous else 'NONE', value['status'])
        if value['status'] == 'REJECTED':
            self.active_hypotheses.pop(hid, None)
            self.rejected_hypotheses[hid] = value
        else:
            self.active_hypotheses[hid] = value
        self.suspected_services = list(dict.fromkeys([h['affected_service'] for h in self.active_hypotheses.values()]))

    def observe_failure(self, name, arguments, error):
        signature = hashlib.sha256(json.dumps([name, arguments, error['error_code']], sort_keys=True).encode()).hexdigest()
        old = self.failure_streak
        self.failure_streak = {'signature':signature, 'name':name, 'arguments':arguments,
            'error_code':error['error_code'], 'count':old.get('count',0)+1 if old.get('signature')==signature else 1}

    def breaker(self, name, arguments):
        old = self.failure_streak
        if old.get('count', 0) >= 2 and old.get('name') == name and old.get('arguments') == arguments:
            return ToolError(error_code='CIRCUIT_BREAKER', message='Two consecutive identical failures; original invocation blocked.',
                actual=old, suggested_action={'change_arguments':True, 'alternative_tools':['search_repository','read_evidence'], 'replan_required':True})

    def pinned(self):
        return serial({'P0':{'validation_errors':self.validation_errors, 'missing_requirements':self.missing_requirements},
            'P1':{'active_hypotheses':self.active_hypotheses, 'critical_evidence':self.critical_evidence,
                  'suspected_services':self.suspected_services, 'unfinished_actions':self.unfinished_actions},
            'control':{'phase':self.phase,'round':self.round,'convergence':self.convergence,
                       'budgets':self.budgets.model_dump(),'last_successful_action':self.last_successful_action,
                       'failure_streak':self.failure_streak,'provider_state':self.provider_state}})

    def rebuild(self, evidence_pack, limit=78000):
        context = {**self.pinned(), 'incident':self.data.get('signal'), 'plan':self.data.get('plan'),
                   'triage':self.data.get('triage'), 'topology':self.data.get('topology'),
                   'evidence':evidence_pack, 'read_registry':self.read_registry,
                   'P2':self.recent_results[-8:], 'P3':self.history[-4:]}
        # Never slice serialized control state. Drop complete low-priority entries.
        while len(json.dumps(serial(context),ensure_ascii=False))>limit and (context['P3'] or context['P2']):
            (context['P3'] or context['P2']).pop(0)
        if len(json.dumps(serial(context),ensure_ascii=False))>limit:
            raise RuntimeFailure(ToolError(error_code='PINNED_CONTEXT_OVERFLOW', retryable=False,
                message='Required control state exceeds context ceiling; nothing silently discarded.'))
        return serial(context)

DETAIL_TOOLS = {'read_evidence','get_trace_detail','get_code_symbol','get_code_context','read_source_file'}
COMPLETION_TOOLS = DETAIL_TOOLS | {'record_hypothesis','submit_root_cause_decision','search_repository',
                                   'inspect_database','inspect_redis','inspect_kafka','get_service_health'}

def offered_names(state, all_names):
    if state.budgets.used.get('exploration',0)>=16 or state.exploration_rounds>=8:
        if state.convergence=='NORMAL': state.convergence='SOFT_CONVERGENCE'
    if state.missing_requirements:
        required={r['required_tool'] for r in state.missing_requirements}
        return set(all_names) & (required | {'submit_root_cause_decision'})
    if state.convergence != 'NORMAL':
        return set(all_names) & COMPLETION_TOOLS
    return set(all_names)

def action_bucket(state, name):
    if name=='submit_root_cause_decision': return 'submission_retry'
    if state.validation_errors or name=='record_hypothesis': return 'correction'
    return 'evidence_completion' if state.convergence!='NORMAL' else 'exploration'

def readiness(state, candidate, evidence):
    missing=[]
    def need(code, tool, arguments, message):
        missing.append({'error_code':code,'required_tool':tool,'suggested_arguments':arguments,'message':message})
    if not state.active_hypotheses:
        need('HYPOTHESIS_NOT_CREATED','record_hypothesis',{'status':'CREATED'},'Create an evidence-grounded hypothesis first.')
    ids=candidate.get('evidence_ids',[]);known={e['id'] for e in evidence}
    if len(set(ids))<2 or any(i not in known or i not in state.read_registry for i in ids):
        need('UNREAD_EVIDENCE','read_evidence',{'evidence_id':next((i for i in ids if i in known and i not in state.read_registry),None)},'Cite at least two valid observations shown to this agent.')
    if candidate.get('affected_service') not in SERVICES:
        need('INVALID_SERVICE','submit_root_cause_decision',{'affected_service':sorted(SERVICES)},'Use a real service name.')
    for location in candidate.get('code_locations',[]):
        if not any(r.get('path')==location['path'] and r.get('start_line',10**9)<=location['start_line']<=location['end_line']<=r.get('end_line',0) for r in state.read_registry.values()):
            need('UNREAD_CITATION','read_source_file',location,'Read the cited source lines before submitting.')
    for name, error in state.validation_errors.items():
        if name=='submit_root_cause_decision': continue  # this attempt revalidates its own previous error
        need('UNRESOLVED_VALIDATION',error.get('suggested_action',{}).get('required_tool',name),{},error['message'])
    state.missing_requirements=missing
    return missing
