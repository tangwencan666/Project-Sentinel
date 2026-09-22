"""Transparent symptom rules. Not an AI fallback, never reads experimental truth."""
import difflib
import json
import uuid
from psycopg.types.json import Jsonb
from services.runtime import query
from .storage import event,evidence_for
from .tool_registry import execute_tool
from .contracts import validate_diagnosis

async def investigate_rules(incident_id,run_id):
    for name,args in [('search_logs',{}),('query_metrics',{}),('get_trace',{}),('get_service_health',{}),('inspect_database',{}),('inspect_redis',{}),('inspect_kafka',{}),('read_source_file',{'path':'services/pricing.py'}),('read_source_file',{'path':'tests/pricing_contract.py'})]:
        await execute_tool(name,args,incident_id,run_id,'RuleBasedInvestigator')
    evidence=await evidence_for(incident_id,run_id)
    data={e['kind']:e['payload'] for e in evidence}
    logs=data.get('search_logs',[]);text=json.dumps(logs)
    db=data.get('inspect_database',{});cache=data.get('inspect_redis',{});queue=data.get('inspect_kafka',[])
    http={s['service']:s for s in data.get('query_metrics',{}).get('http',[])}
    category,service,root='UNKNOWN','unknown','No rule has sufficient supporting observations.'
    relevant=['search_logs','query_metrics']
    if 'NoneType' in text and 'TypeError' in text:
        category,service,root='CODE_EXCEPTION','order-service','Nullable discount reaches arithmetic that subtracts None from an integer.'
        relevant=['search_logs','read_source_file']
    elif 'PoolTimeout' in text:
        category,service,root='DB_POOL_EXHAUSTION','inventory-service','Inventory requests time out acquiring pooled database connections.'
        relevant=['search_logs','get_service_health','inspect_database']
    elif sum(p.get('lag',0) for p in queue)>5:
        category,service,root='CONSUMER_LAG','notification-service','Notification committed offsets fall behind produced order offsets.'
        relevant=['inspect_kafka','query_metrics']
    elif http.get('payment-service',{}).get('requests',0)>3*max(http.get('order-service',{}).get('requests',0),1) and any(r['service']=='payment-service' and r['status']==503 for r in logs):
        category,service,root='RETRY_AMPLIFICATION','order-service','Failed payment calls are amplified by repeated upstream retry attempts.'
    elif float(http.get('payment-service',{}).get('p95_ms',0))>2500:
        category,service,root='DOWNSTREAM_TIMEOUT','payment-service','Payment latency exceeds the upstream request deadline.'
        relevant=['query_metrics','get_trace','search_logs']
    elif any(s.get('wait_event')=='PgSleep' and s.get('state')=='active' for s in db.get('activity',[])) or any('pg_sleep' in s['query'] and (s['calls_delta'] or 0)>0 for s in db.get('call_deltas',[])):
        category,service,root='DATABASE_SLOW_QUERY','inventory-service','Database execution is delayed by active sleeping SQL statements.'
        relevant=['inspect_database','query_metrics']
    elif any('WHERE id=' in s['query'] and (s['calls_delta'] or 0)>=20 for s in db.get('call_deltas',[])):
        category,service,root='N_PLUS_ONE','inventory-service','Catalog retrieval performs repeated per-product queries instead of a batch query.'
        relevant=['inspect_database','query_metrics','get_trace']
    elif cache.get('catalog_ttl')==-2 and any('FROM products' in s['query'] and (s['calls_delta'] or 0)>0 for s in db.get('call_deltas',[])):
        category,service,root='CACHE_MISS','inventory-service','Missing catalog cache causes requests to repeatedly reach the database.'
        relevant=['inspect_redis','inspect_database']
    ids=[e['id'] for e in evidence if e['kind'] in relevant]
    diagnosis={'hypothesis':root,'affected_service':service,'root_cause':root,'category':category,'evidence_ids':ids,'code_locations':[],'reasoning_summary':'RULE_BASED: matched explicit telemetry predicates; no LLM inference. '+root,'recommended_fix':'Investigate and remove the measured failure mechanism; a rule match is not proof of causality.','remaining_uncertainty':['Rules may confuse concurrent faults and do not establish causal counterfactuals.'],'patch_decision':'NO_CODE_PATCH'}
    if category=='CODE_EXCEPTION':
        from .patching import BASE
        source=BASE.read_text()
        if '(1 - discount)' in source:
            diagnosis.update(patch_decision='CODE_PATCH',code_locations=[{'path':'services/pricing.py','start_line':3,'end_line':6}],recommended_fix='Normalize nullable discount to zero before arithmetic.')
            from .ai_patching import validate_ai_diff
            candidate=source.replace('(1 - discount)','(1 - (discount if discount is not None else 0))')
            diff=''.join(difflib.unified_diff(source.splitlines(True),candidate.splitlines(True),fromfile='a/services/pricing.py',tofile='b/services/pricing.py'))
            artifact=await validate_ai_diff(diff,incident_id);artifact['origin']='RULE_BASED'
            await query('INSERT INTO ai_patches(id,incident_id,run_id,origin,status,artifact) VALUES(%s,%s,%s,%s,%s,%s)',(str(uuid.uuid4()),incident_id,run_id,'RULE_BASED',artifact['status'],Jsonb(artifact)))
            await event(incident_id,'Rule Patch Tested',{'origin':'RULE_BASED','status':artifact['status'],'candidate_verified':artifact['candidate_verified']},'RuleBasedInvestigator',run_id)
    validate_diagnosis(diagnosis,evidence)
    await event(incident_id,'Rule Diagnosis',diagnosis,'RuleBasedInvestigator',run_id)
    return diagnosis
