"""Durable, bounded capability execution for V3.1+. No experiment-label imports."""
import ast
import asyncio
import difflib
import json
import hashlib
import uuid
from pydantic import Field
from psycopg.types.json import Jsonb
from services.runtime import query
from . import tool_registry as registry
from .hybrid_tools import HYBRID_TOOLS, RootCauseDecision
from .contracts import check_citations
from .context_engineering import summarize
from .runtime_state import (RuntimeHypothesis, ToolError, RuntimeFailure, readiness,
                            action_bucket, DETAIL_TOOLS)
from .structured_output import parse_validate
from .security import serial
from .storage import event, evidence_for
from .context_delivery import detail_page,raw_evidence_page
from .submission_contract import CompactRootCauseDecision
from .budget_accounting import result_bucket

class TracePage(registry.Trace):
    offset:int=Field(default=0,ge=0)
    limit:int=Field(default=8,ge=1,le=12)

class EvidencePage(registry.EvidenceRead):
    length:int=Field(default=4,ge=1,le=12,description='Number of complete JSON records, not characters.')

SCHEMAS={n:s for n,(s,_) in registry.DEFINITIONS.items()}
SCHEMAS['record_hypothesis']=RuntimeHypothesis
SCHEMAS['get_trace_detail']=TracePage
SCHEMAS['submit_root_cause_decision']=CompactRootCauseDecision
NAMES={t['function']['name'] for t in HYBRID_TOOLS} | {'read_source_file'}
NAMES-={'run_deterministic_triage'}

def schema_for(state,name):
    return EvidencePage if state.version in ('4','4.1') and name=='read_evidence' else SCHEMAS[name]
def tools_for(names,state=None):
    tools=[{'type':'function','function':{'name':n,'description':registry.DEFINITIONS[n][1],
            'parameters':SCHEMAS[n].model_json_schema()}} for n in sorted(names)]
    if state:
        actual=[s['signal_id'] for s in state.data.get('triage',{}).get('signals',[])]
        for tool in tools:
            if tool['function']['name']=='submit_root_cause_decision':
                schema=tool['function']['parameters']
                schema['properties']['deterministic_signals']['maxItems']=len(actual)
                if actual: schema['$defs']['CompactSignalAssessment']['properties']['signal_id']['enum']=actual
            if state.version in ('4','4.1') and tool['function']['name']=='read_evidence':
                tool['function']['parameters']=EvidencePage.model_json_schema()
                tool['function']['description']='Read immutable raw evidence as complete JSON records with paths. offset/length count objects. Continue with next_offset; no summarization.'
    return tools

def symbol_candidates(symbol):
    rows=[]
    for path in sorted(registry.SOURCE_FILES):
        for node in ast.walk(ast.parse(registry.source_path(path).read_text())):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                rows.append({'path':path,'symbol':node.name,'start_line':node.lineno,'end_line':node.end_lineno})
    return sorted(rows,key=lambda x:difflib.SequenceMatcher(None,symbol,x['symbol']).ratio(),reverse=True)[:6]

async def receipt(run_id, external_id):
    row=await query('SELECT payload FROM runtime_tool_receipts WHERE run_id=%s AND external_id=%s',(run_id,external_id),one=True)
    return row['payload'] if row else None

def register_read(state, item):
    payload=item['payload'];entry={'kind':item['kind'],'read':True}
    if isinstance(payload,dict) and all(k in payload for k in ('path','start_line','end_line')):
        entry.update({k:payload[k] for k in ('path','start_line','end_line')})
    state.read_registry[item['id']]=entry

async def reconcile(state, name, arguments, result):
    """Idempotent application after the receipt commits, including process crash recovery."""
    call_id=result['tool_call_id']
    processed=state.data.setdefault('processed_receipts',[])
    if call_id in processed: return
    if result.get('budget_bucket'): state.budgets.consume(result['budget_bucket'])
    state.tool_calls+=1
    if result.get('error'):
        state.pin_error(name,result['error'])
        if result['error']['error_code']!='CIRCUIT_BREAKER': state.observe_failure(name,arguments,result['error'])
    else:
        state.resolve(name);state.failure_streak={}
        state.last_successful_action={'tool':name,'arguments':arguments,'tool_call_id':call_id}
        if name=='record_hypothesis':
            value=result['result']['hypothesis']
            # DB commit can precede checkpoint; restoring this receipt must not reapply the FSM.
            target=state.rejected_hypotheses if value['status']=='REJECTED' else state.active_hypotheses
            target[value['hypothesis_id']]=value
            if value['status']=='REJECTED': state.active_hypotheses.pop(value['hypothesis_id'],None)
            state.suspected_services=list(dict.fromkeys(h['affected_service'] for h in state.active_hypotheses.values()))
            cited={i for h in state.active_hypotheses.values() for i in h['evidence_ids']}
            evidence=await evidence_for(state.incident_id,state.run_id)
            from .evidence_compiler import compile_observation
            compiler=compile_observation if state.version in ('4','4.1') else summarize
            state.critical_evidence={e['id']:{'kind':e['kind'],'observations':compiler(e['kind'],e['payload'])} for e in evidence if e['id'] in cited}
        if name=='submit_root_cause_decision':
            state.data['decision']=result['result']['decision'];state.convergence='SUBMIT'
        # Capability execution is not proof that the model saw the output.
        # Runner records visible reads only after the actual provider request succeeds.
    processed.append(call_id)

async def execute(state, name, raw_arguments, external_id, allowed, persist, actor='Investigator'):
    try: identity_arguments=json.loads(raw_arguments) if isinstance(raw_arguments,str) else raw_arguments
    except ValueError: identity_arguments=raw_arguments
    fingerprint=hashlib.sha256(json.dumps(serial([name,identity_arguments]),sort_keys=True).encode()).hexdigest()
    previous=await receipt(state.run_id,external_id)
    if previous:
        if previous.get('request_fingerprint') and previous['request_fingerprint']!=fingerprint:
            raise RuntimeFailure(ToolError(error_code='TOOL_RECEIPT_MISMATCH',retryable=False,
                message='A completed call ID cannot be reused for different arguments or capability.'))
        try: recovered_args=json.loads(raw_arguments) if isinstance(raw_arguments,str) else raw_arguments
        except ValueError: recovered_args=raw_arguments
        await reconcile(state,name,recovered_args,previous)
        if previous.get('error',{}).get('retryable') is False:
            raise RuntimeFailure(ToolError(**previous['error']))
        return previous
    call_id=str(uuid.uuid4());args=raw_arguments;error=None;result=None;ids=[]
    await query('INSERT INTO tool_calls(id,external_id,incident_id,run_id,agent,tool_name,arguments,status) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',
                (call_id,external_id,state.incident_id,state.run_id,actor,name,Jsonb(serial(raw_arguments)),'started'))
    await event(state.incident_id,'Tool Started',{'tool_call_id':call_id,'tool':name,'arguments':raw_arguments},actor,state.run_id)
    try:
        if len(json.dumps(raw_arguments,ensure_ascii=False))>20000:
            raise RuntimeFailure(ToolError(error_code='OVERSIZED_ARGUMENTS',retryable=False,message='Tool arguments exceed 20,000 characters.'))
        try: comparable=json.loads(raw_arguments) if isinstance(raw_arguments,str) else raw_arguments
        except ValueError: comparable=raw_arguments
        args=comparable
        broken=state.breaker(name,comparable)
        if broken: raise RuntimeFailure(broken)
        if name not in allowed or name not in NAMES:
            raise RuntimeFailure(ToolError(error_code='TOOL_NOT_AVAILABLE_IN_PHASE',message='Choose an offered capability.',
                expected=sorted(allowed),actual=name,suggested_action={'change_arguments':True,'alternative_tools':sorted(allowed)}))
        args=parse_validate(raw_arguments,schema_for(state,name))
        if name=='submit_root_cause_decision':
            known={s['signal_id'] for s in state.data.get('triage',{}).get('signals',[])}
            submitted=[s['signal_id'] for s in args['deterministic_signals']]
            if any(s not in known for s in submitted) or len(submitted)!=len(set(submitted)):
                raise RuntimeFailure(ToolError(error_code='SCHEMA_VALIDATION_FAILED',
                    message='Use each supplied triage signal_id at most once; never invent signals.',
                    invalid_fields=['deterministic_signals'],expected=sorted(known),actual=submitted,
                    suggested_action={'required_tool':name,'repair':'Copy actual signal IDs; empty array when none exist.'}))
        broken=state.breaker(name,args)
        if broken: raise RuntimeFailure(broken)
        bucket=action_bucket(state,name)
        if state.budgets.used.get(bucket,0)>=state.budgets.limits[bucket]:
            raise RuntimeFailure(ToolError(error_code='BUDGET_EXHAUSTED',retryable=False,message=f'{bucket} budget exhausted before invocation.'))
        if name=='record_hypothesis':
            evidence=await evidence_for(state.incident_id,state.run_id)
            check_citations(args['evidence_ids'],evidence)
            copy=state.model_copy(deep=True);copy.apply_hypothesis(args)
            hid=state.run_id+':'+args['hypothesis_id']
            await query('INSERT INTO hypotheses(id,incident_id,run_id,status,payload) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET status=excluded.status,payload=excluded.payload,updated_at=now()',
                (hid,state.incident_id,state.run_id,args['status'],Jsonb(serial(args))))
            result={'hypothesis':args}
            await event(state.incident_id,'Hypothesis '+args['status'].title(),args,'Investigator',state.run_id)
        else:
            if name=='submit_root_cause_decision':
                missing=readiness(state,args,await evidence_for(state.incident_id,state.run_id))
                if missing:
                    first=missing[0]
                    raise RuntimeFailure(ToolError(error_code=first['error_code'],message=first['message'],
                        expected={'MissingRequirements':missing},suggested_action={k:first[k] for k in ('required_tool','suggested_arguments')}))
                if args['contradicting_evidence'] and args['category']!='UNKNOWN':
                    raise RuntimeFailure(ToolError(error_code='UNRESOLVED_CONTRADICTION',
                        message='The submitted observations are marked as unresolved evidence AGAINST the cause. Re-read them, obtain bounded corroboration, or submit UNKNOWN; excluded alternatives and historical counters are not automatically contradictions.',
                        invalid_fields=['contradicting_evidence','category'],actual={'evidence_ids':args['contradicting_evidence']},
                        expected='Resolve the contradiction from evidence, or preserve uncertainty with category UNKNOWN.',
                        suggested_action={'required_tool':'read_evidence','suggested_arguments':{'evidence_id':args['contradicting_evidence'][0]},
                            'alternative_tools':['read_source_file','get_code_symbol','get_code_context','get_trace_detail','record_hypothesis','submit_root_cause_decision']}))
                state.convergence='SUBMISSION_READY'
            if state.version in ('4','4.1') and name=='read_evidence':
                item=await query('SELECT payload FROM evidence_items WHERE id=%s AND incident_id=%s AND run_id=%s',
                                 (args['evidence_id'],state.incident_id,state.run_id),one=True)
                if not item: raise ValueError('unknown evidence in this investigation')
                result={'evidence_id':args['evidence_id'],**raw_evidence_page(item['payload'],args['offset'],args['length'])}
            elif name=='get_trace_detail':
                traces=await asyncio.wait_for(registry.adapters.traces(args['trace_id']),25)
                result=serial(detail_page(traces,args['offset'],args['limit']))
            else:
                result=serial(await asyncio.wait_for(registry.invoke(name,args,state.incident_id,state.run_id),25))
            if name=='search_repository' and not result['matches']:
                result['symbol_candidates']=symbol_candidates(args['text'])
            if name!='read_evidence':
                eid='E-'+uuid.uuid4().hex[:16];ids=[eid]
                await query('INSERT INTO evidence_items(id,incident_id,run_id,tool_call_id,kind,payload) VALUES(%s,%s,%s,%s,%s,%s)',
                    (eid,state.incident_id,state.run_id,call_id,name,Jsonb(result)))
                await event(state.incident_id,'Evidence Added',{'evidence_id':eid,'tool':name,'source':'Repository' if 'code' in name or 'source' in name else 'Measured'},'Investigator',state.run_id)
    except RuntimeFailure as exc: error=exc.error
    except asyncio.TimeoutError:
        error=ToolError(error_code='TOOL_TIMEOUT',message='Tool exceeded its 25-second deadline.',suggested_action={'required_tool':name,'retry':True})
    except Exception as exc:
        if name=='get_code_symbol' and str(exc)=='symbol not found':
            error=ToolError(error_code='SYMBOL_NOT_FOUND',message='Symbol absent from repository AST index.',
                actual=args.get('symbol'),expected=symbol_candidates(args.get('symbol','')),
                suggested_action={'required_tool':'get_code_symbol','candidates':symbol_candidates(args.get('symbol',''))})
        else:
            error=ToolError(error_code='TOOL_FAILURE',message=str(exc),suggested_action={'required_tool':name,'change_arguments':True})
    # Errors consume correction, never exploration; all categories remain globally bounded.
    bucket=result_bucket(state,name,error)
    if state.budgets.used.get(bucket,0)>=state.budgets.limits[bucket]:
        error=ToolError(error_code='BUDGET_EXHAUSTED',retryable=False,message=f'{bucket} budget exhausted.',
            actual={'budget':bucket,'underlying_error':error.model_dump() if error else None});bucket=None
    payload=serial({'tool_call_id':call_id,'evidence_ids':ids,'error':error.model_dump()} if error else
                   {'tool_call_id':call_id,'evidence_ids':ids,'result':result})
    payload['budget_bucket']=bucket
    payload['request_fingerprint']=fingerprint
    await query("UPDATE tool_calls SET finished_at=now(),status=%s,arguments=%s,error=%s,evidence_ids=%s,result_summary=%s WHERE id=%s",
        ('failed' if error else 'succeeded',Jsonb(serial(args)),Jsonb(serial(error.model_dump())) if error else None,Jsonb(ids),json.dumps(serial(result),ensure_ascii=False)[:700],call_id))
    await query('INSERT INTO runtime_tool_receipts(tool_call_id,run_id,external_id,payload) VALUES(%s,%s,%s,%s)',
        (call_id,state.run_id,external_id,Jsonb(payload)))
    await reconcile(state,name,args,payload)
    await event(state.incident_id,'Tool Error' if error else 'Tool Finished',{'tool':name,**payload} if error else {'tool':name,'tool_call_id':call_id,'evidence_ids':ids},actor,state.run_id)
    await persist()
    if error and not error.retryable: raise RuntimeFailure(error)
    return payload

async def model_result(state,name,result):
    if result.get('error') or name in DETAIL_TOOLS or not result.get('evidence_ids'): return result
    from .context_engineering import evidence_pack
    rows=await query('SELECT * FROM evidence_items WHERE run_id=%s AND id=ANY(%s)',(state.run_id,result['evidence_ids']))
    if state.version in ('4','4.1'):
        from .evidence_compiler import compile_pack
        packed,_=compile_pack(rows,6500,state.suspected_services)
        return {'tool_call_id':result['tool_call_id'],'evidence_ids':result['evidence_ids'],
                'result':packed['items'],'raw_retrieval':'read_evidence','compressed':True,
                'omitted_items':packed['omitted_items']}
    return {'tool_call_id':result['tool_call_id'],'evidence_ids':result['evidence_ids'],
            'result':evidence_pack(rows,4200)['items'],'raw_retrieval':'read_evidence','compressed':True}
