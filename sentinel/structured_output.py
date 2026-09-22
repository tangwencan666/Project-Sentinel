"""Bounded JSON/schema repair. Boundary fixtures test protocol, never model accuracy."""
import json
from pydantic import ValidationError
from psycopg.types.json import Jsonb
from services.runtime import query
from .runtime_state import ToolError, RuntimeFailure
from .security import serial
from . import field_repair

def parse_validate(raw, schema):
    try:
        obj=json.loads(raw or '') if isinstance(raw,(str,type(None))) else raw
    except (ValueError,TypeError) as exc:
        raise RuntimeFailure(ToolError(error_code='INVALID_ARGUMENT_JSON', message=str(exc),
            invalid_fields=['JSON'], expected='one complete JSON object',
            suggested_action={'repair':'Return corrected JSON only; preserve evidence and uncertainty.'})) from None
    try:
        return schema.model_validate(obj).model_dump()
    except ValidationError as exc:
        errors=exc.errors(include_url=False,include_input=False)
        code='FIELD_TOO_LONG' if any(e['type'] in ('string_too_long','too_long') for e in errors) else 'SCHEMA_VALIDATION_FAILED'
        raise RuntimeFailure(ToolError(error_code=code,message='Output does not satisfy schema.',
            invalid_fields=['.'.join(map(str,e['loc'])) for e in errors],expected=errors,
            suggested_action={'repair':'Correct the named fields; return an instance, not a JSON schema.'})) from None

async def mark_parse(metadata, error=None):
    if not metadata or not metadata.get('call_id'): return
    schema_error=error and error.error_code in ('INVALID_ARGUMENT_JSON','SCHEMA_VALIDATION_FAILED','FIELD_TOO_LONG')
    if not schema_error and metadata.get('parse_status')=='invalid': return
    status={'parse_status':'invalid' if schema_error else 'valid',
            'parse_error':error.model_dump() if error and error.error_code=='INVALID_ARGUMENT_JSON' else None,
            'schema_error':error.model_dump() if schema_error and error.error_code!='INVALID_ARGUMENT_JSON' else None}
    metadata.update(status)
    await query("UPDATE llm_calls SET diagnostics=coalesce(diagnostics,'{}'::jsonb)||%s WHERE id=%s",
                (Jsonb(serial(status)),metadata['call_id']))

async def structured(messages, schema, invoke, state, stage, persist, record, repair_seed=None):
    """One original response + at most two repairs, bounded across checkpoints."""
    job=state.data.setdefault('structured_jobs',{}).setdefault(stage,{'attempt':0,'messages':messages})
    if 'result' in job: return job['result']
    if job['attempt']>=3:
        raise RuntimeFailure(ToolError(**job['last_error']))
    if repair_seed is not None and 'field_repair' not in job:
        prepared=field_repair.prepare(repair_seed,job.get('last_error',{}))
        if prepared:
            job['field_repair']=prepared;job['messages']=field_repair.messages(prepared)
            await record('Field Repair Planned',{'stage':stage,'fields':[{k:f[k] for k in ('path','current_characters','maximum_characters','target_characters')} for f in prepared['fields']]})
    while job['attempt']<3:
        if job['attempt'] and job['attempt'] not in job.setdefault('charged_attempts',[]):
            state.budgets.consume('schema_repair')
            job['charged_attempts'].append(job['attempt'])
            await record('Schema Repair',{'stage':stage,'attempt':job['attempt'],'error':job['last_error']})
        await persist()
        response=await invoke(job['messages'])
        metadata=response.get('_runtime',{})
        state.provider_state=metadata
        job['attempt']+=1
        job.setdefault('response_call_ids',[]).append(metadata.get('call_id'))
        try:
            raw=response.get('content')
            if job.get('field_repair'):
                try: raw=field_repair.apply(raw,job['field_repair'])
                except (ValueError,TypeError) as exc:
                    raise RuntimeFailure(ToolError(error_code='INVALID_ARGUMENT_JSON' if isinstance(exc,json.JSONDecodeError) else 'SCHEMA_VALIDATION_FAILED',
                        message=str(exc),actual=getattr(exc,'details',None),invalid_fields=['replacements'],suggested_action={'repair':'Return only all requested shorter field replacements.'})) from None
            value=parse_validate(raw,schema)
            await mark_parse(metadata)
            job['result']=value
            state.resolve(stage)
            await persist()
            return value
        except RuntimeFailure as exc:
            await mark_parse(metadata,exc.error)
            job['last_error']=exc.public()
            state.pin_error(stage,exc.error)
            # Schema plus concrete validation feedback; raw output is untrusted data.
            prepared=job.get('field_repair') or field_repair.prepare(response.get('content'),exc.public())
            if prepared:
                job['field_repair']=prepared;job['messages']=field_repair.messages(prepared,exc.public())
            else:
                job['messages']=[messages[0],{'role':'user','content':json.dumps(serial({
                    'original_request':messages[1:],'invalid_output':response.get('content'),
                    'validation_error':exc.public(),'finish_reason':metadata.get('finish_reason'),
                    'instruction':'Rewrite a shorter complete JSON object within the existing output ceiling; preserve actual evidence IDs and uncertainty. Do not invent missing evidence.'}),ensure_ascii=False)}]
            await record('Structured Output Error',{'stage':stage,'attempt':job['attempt'],'error':exc.public()})
            await persist()
            if job['attempt']>=3: raise

def planner_fallback(triage):
    signals=triage.get('signals',[])
    def observed_strength(signal):
        rows=signal.get('observations',{})
        if not isinstance(rows,list): rows=[rows]
        scores=[]
        for row in rows:
            if not isinstance(row,dict): continue
            for key,scale in [('error_pct',100),('p95_ms',1000),('requests_waiting',1),('lag_delta',5),('request_ratio',2)]:
                if isinstance(row.get(key),(int,float,str)):
                    try: scores.append(abs(float(row[key]))/scale)
                    except ValueError: pass
        return max(scores,default=0),len(signal.get('evidence_ids',[]))
    signal=max(signals,key=observed_strength,default={})
    services=signal.get('suspected_services') or ([signal['service']] if signal.get('service') else triage.get('suspected_services',[]))
    return {'suspected_services':services[:6],
            'initial_hypotheses':['Investigate the strongest measured triage anomaly; cause remains unconfirmed.'],
            'tool_priority':['read_evidence','inspect_database','inspect_redis','inspect_kafka','get_trace','record_hypothesis'],
            'stop_conditions':['Two independent sources support a bounded claim, or submit UNKNOWN with uncertainty.']}
