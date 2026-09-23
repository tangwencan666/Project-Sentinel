"""Advisory triage and topology capabilities. No experiment/control/evaluation imports."""
import asyncio
import ast
import json
import time
from pathlib import Path
from typing import Literal,Annotated
from urllib.parse import urlsplit
import httpx
from pydantic import Field
from services.runtime import query
from .contracts import Strict,Diagnosis,validate_diagnosis
from .context_engineering import independent_sources,trace_summary
from .storage import evidence_for
from . import tool_registry as registry


class InvestigationPlan(Strict):
    suspected_services:list[str]=Field(max_length=6)
    initial_hypotheses:list[str]=Field(max_length=4)
    tool_priority:list[str]=Field(max_length=8)
    stop_conditions:list[str]=Field(max_length=4)

EvidenceID=Annotated[str,Field(pattern=r'^E-[0-9a-f]{16}$')]


class SignalAssessment(Strict):
    signal_id:str
    disposition:Literal['supported','refuted','uncertain']
    evidence_ids:list[EvidenceID]
    explanation:str=Field(max_length=700)


class RootCauseDecision(Diagnosis):
    supporting_evidence:list[EvidenceID]=Field(min_length=2,description='Bare existing Evidence IDs only, exactly E- plus 16 lowercase hex digits. No explanations or suffixes. Put findings in llm_findings.')
    contradicting_evidence:list[EvidenceID]=Field(description='Bare Evidence IDs for unresolved observations AGAINST this proposed cause. Ruled-out alternative causes or healthy unrelated components are not contradictions. Empty if none.')
    deterministic_signals:list[SignalAssessment]
    llm_findings:list[str]=Field(max_length=6)


class Symbol(Strict):
    path:str
    symbol:str=Field(min_length=1,max_length=100)


class Context(Strict):
    path:str
    line:int=Field(ge=1)
    surrounding_lines:int=Field(default=8,ge=0,le=20)


def code_symbol(path,symbol):
    tree=ast.parse(registry.source_path(path).read_text())
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and node.name==symbol:
            return registry.read_source(path,node.lineno,min(node.end_lineno,node.lineno+79))
    raise ValueError('symbol not found')


def topology_from_traces(traces):
    edges={}
    for trace in traces:
        for span in trace.get('spans',[]):
            tags={t['key']:t.get('value') for t in span.get('tags',[])}
            source=trace.get('processes',{}).get(span['processID'],{}).get('serviceName')
            target=urlsplit(tags.get('http.url','')).hostname or tags.get('net.peer.name')
            if source and target and source!=target:
                edges[(source,target)]={'source':source,'target':target,'provenance':'observed_span',
                    'trace_id':trace['traceID'],'span_id':span.get('spanID')}
    # Role configuration is architecture, not telemetry or an inferred root cause.
    for service in registry.adapters.SERVICES:
        for target in ('postgres','redis'):
            edges.setdefault((service,target),{'source':service,'target':target,
                'provenance':'configured shared runtime pool/redis; services/runtime.py'})
    for source,target in (('order-service','redpanda'),('redpanda','notification-service')):
        edges.setdefault((source,target),{'source':source,'target':target,
            'provenance':'configured producer/consumer lifecycle; services/app.py'})
    return {'nodes':registry.adapters.SERVICES+['postgres','redis','redpanda'],'edges':list(edges.values()),
        'limitations':'HTTP edges are sampled observed paths; absent edge is not proof of no dependency. Pricing is a function in order-service, not a microservice.'}


async def metric_windows(incident_id):
    incident=await query('SELECT created_at FROM incidents WHERE id=%s',(incident_id,),one=True)
    end=time.time();baseline_at=incident['created_at'].timestamp()-30
    queries={'db_qps':'sum by(service)(rate(commerce_db_queries_total[1m]))',
             'request_rps':'sum by(service)(rate(commerce_requests_total[1m]))'}
    windows=[]
    async with httpx.AsyncClient(timeout=5) as client:
        for metric,q in queries.items():
            current=await client.get('http://prometheus:9090/api/v1/query_range',params={'query':q,'start':end-20,'end':end,'step':5})
            previous=await client.get('http://prometheus:9090/api/v1/query',params={'query':q,'time':baseline_at})
            current.raise_for_status();previous.raise_for_status()
            bases={r['metric']['service']:float(r['value'][1]) for r in previous.json().get('data',{}).get('result',[])}
            for row in current.json().get('data',{}).get('result',[]):
                service=row['metric']['service']
                windows.append({'metric':metric,'service':service,'baseline':bases.get(service),
                    'baseline_at':baseline_at,'values':[float(v[1]) for v in row['values']],
                    'timestamps':[v[0] for v in row['values']],'baseline_health':'unconfirmed pre-incident window'})
    return windows


def derive_signals(observations):
    """Only measured predicates. No final cause categories or scenario identifiers."""
    signals=[]
    def add(label,services,kinds,detail,tools):
        ids=[eid for k in kinds for eid in observations.get(k,{}).get('ids',[])]
        if any(s['signal']==label and s['suspected_services']==services for s in signals): return
        signals.append({'signal_id':'S'+str(len(signals)+1),'signal':label,'suspected_services':services,
                        'evidence_ids':ids,'observations':detail,'recommended_next_tools':tools})
    data=lambda name:observations.get(name,{}).get('data')
    metrics=data('query_metrics') or {};http={r['service']:r for r in metrics.get('http',[])}
    for service,row in http.items():
        if float(row['error_pct'])>10 or row['p95_ms']>1000:
            add('HTTP errors or latency elevated',[service],['query_metrics'],row,['search_logs','get_trace_detail'])
    cache=data('inspect_redis') or {};db=data('inspect_database') or {}
    moving=[r for r in db.get('call_deltas',[]) if (r.get('calls_delta') or 0)>0]
    if cache.get('catalog_ttl')==-2 and any('FROM products' in r['query'] and (r['calls_delta'] or 0)>2 for r in moving):
        add('Possible cache effectiveness degradation',['inventory-service'],['inspect_redis','inspect_database'],
            {'catalog_ttl':-2,'moving_sql':moving,'redis_counter_scope':'shared counters include control traffic'},['inspect_redis','query_metrics','get_trace'])
    for pool in data('get_service_health') or []:
        stats=pool.get('pool-stats',{}).get('body',{}).get('pool',{})
        if stats.get('requests_waiting',0)>0 or (stats.get('pool_size',0)>0 and stats.get('pool_available',1)==0):
            add('Possible DB connection pressure',[pool['service']],['get_service_health'],stats,['search_logs','inspect_database'])
    before=data('queue_before') or [];after=data('inspect_kafka') or []
    if before and after:
        old={p['partition']:p for p in before};sample=observations.get('queue_sample_seconds',1)
        changes=[{'partition':p['partition'],'lag':p['lag'],'lag_delta':p['lag']-old[p['partition']]['lag'],
                  'producer_rps':(p['end_offset']-old[p['partition']]['end_offset'])/sample,
                  'consumer_rps':(p['committed_offset']-old[p['partition']]['committed_offset'])/sample if p['committed_offset'] is not None and old[p['partition']]['committed_offset'] is not None else None}
                 for p in after if p['partition'] in old]
        if any(c['lag']>5 and c['lag_delta']>0 for c in changes):
            add('Possible consumer-side processing issue',['notification-service'],['queue_before','inspect_kafka'],changes,['inspect_kafka','search_logs','get_service_topology'])
    traces=trace_summary(data('get_trace') or [])
    for trace in traces:
        for repeated in trace['repeated_calls']:
            target=urlsplit(repeated['endpoint']).hostname;caller=repeated['caller']
            ratio=float(http.get(target,{}).get('throughput_rps',0))/max(float(http.get(caller,{}).get('throughput_rps',0)),.001)
            if ratio>2 and repeated['count']>1:
                add('Possible request retry amplification',[caller],['get_trace','query_metrics'],
                    {**repeated,'downstream_service':target,'request_ratio':ratio,'trace_id':trace['trace_id']},['get_trace_detail','search_logs'])
                break
    return {'signals':signals,'evidence_ids':sorted({i for s in signals for i in s['evidence_ids']}),
            'suspected_services':sorted({s for item in signals for s in item['suspected_services']}),
            'recommended_next_tools':list(dict.fromkeys(t for s in signals for t in s['recommended_next_tools'])),
            'advisory_only':True,'warning':'Deterministic triage is advisory evidence, not ground truth. HTTP health does not establish queue/cache health.'}


async def triage(incident_id,run_id):
    observations={};clock=time.monotonic()
    for name,args,key in [('inspect_kafka',{},'queue_before'),('query_metrics',{},'query_metrics'),
        ('inspect_database',{},'inspect_database'),('inspect_redis',{},'inspect_redis'),
        ('get_service_health',{},'get_service_health'),('get_trace',{},'get_trace'),('inspect_kafka',{},'inspect_kafka')]:
        result=await registry.execute_tool(name,args,incident_id,run_id,'Triage')
        ids=result.get('evidence_ids',[])
        rows=await evidence_for(incident_id,run_id)
        payload=next((e['payload'] for e in rows if e['id'] in ids),None)
        observations[key]={'ids':ids,'data':payload,'error':result.get('error')}
    observations['queue_sample_seconds']=max(time.monotonic()-clock,.001)
    return derive_signals(observations)


async def invoke(name,args,incident_id,run_id):
    if name=='run_deterministic_triage': return await triage(incident_id,run_id)
    if name in ('get_service_topology','get_upstream_services','get_downstream_services'):
        existing=await evidence_for(incident_id,run_id)
        traces=next((e['payload'] for e in reversed(existing) if e['kind'] in ('get_trace','get_trace_detail')),[])
        topology=topology_from_traces(traces)
        if name=='get_service_topology': return topology
        service=args.get('service')
        if service not in topology['nodes']: raise ValueError('unknown service')
        topology['edges']=[e for e in topology['edges'] if e['target' if name=='get_upstream_services' else 'source']==service]
        return topology
    if name=='get_trace_detail': return await registry.adapters.traces(args['trace_id'])
    if name=='get_code_symbol': return code_symbol(**args)
    if name=='get_code_context': return registry.read_source(args['path'],max(1,args['line']-args['surrounding_lines']),args['line']+args['surrounding_lines'])
    if name=='submit_root_cause_decision':
        decision=RootCauseDecision.model_validate(args);evidence=await evidence_for(incident_id,run_id)
        validate_diagnosis({k:v for k,v in args.items() if k in Diagnosis.model_fields},evidence)
        if len(independent_sources(decision.supporting_evidence,evidence))<2:
            available=[{'id':e['id'],'kind':e['kind']} for e in evidence if e['kind'] in ('search_logs','query_metrics','inspect_database','inspect_redis','inspect_kafka','get_trace','get_trace_detail','get_service_health')][-12:]
            raise ValueError('Cite bare IDs from at least two independent source families; triage/topology do not count. Available observations: '+json.dumps(available))
        known={e['id'] for e in evidence}
        if any(i not in known or i not in decision.evidence_ids for i in decision.supporting_evidence): raise ValueError('supporting evidence must be valid diagnosis citations')
        if any(i not in known for i in decision.contradicting_evidence): raise ValueError('unknown contradictory evidence')
        if decision.contradicting_evidence and decision.category!='UNKNOWN': raise ValueError('resolve strong conflicting evidence before asserting a root cause, or report UNKNOWN with uncertainty')
        if not await query('SELECT id FROM hypotheses WHERE run_id=%s',(run_id,)): raise ValueError('record a hypothesis first')
        return {'decision':decision.model_dump()}
    raise ValueError('unknown hybrid capability')


EXTRA={
    'run_deterministic_triage':(registry.Empty,'Collect fresh audited infrastructure observations and derive advisory signals; not a final diagnosis.'),
    'get_service_topology':(registry.Empty,'Observed trace dependencies plus explicitly configured infrastructure edges; pricing is an order-service function.'),
    'get_upstream_services':(registry.Service,'Read caller dependencies of a service from the observed topology.'),
    'get_downstream_services':(registry.Service,'Read downstream dependencies; follow failed span paths before querying unrelated services.'),
    'get_trace_detail':(registry.Trace,'Retrieve raw spans for one observed trace ID on demand.'),
    'get_code_symbol':(Symbol,'Read one actual allowlisted source function or class, bounded to 80 lines.'),
    'get_code_context':(Context,'Read limited surrounding source lines from an allowlisted file.'),
    'submit_root_cause_decision':(RootCauseDecision,'Finish after recording a hypothesis; fuse evidence, triage assessments, contrary evidence, and uncertainty. Stop when two independent sources corroborate and strong conflicts are resolved.'),
}
registry.DEFINITIONS.update(EXTRA)
registry.CUSTOM_HANDLERS.update({name:invoke for name in EXTRA})
HYBRID_TOOLS=[t for t in registry.TOOLS if t['function']['name'] not in
              ('complete_investigation','submit_verification','generate_diff','validate_patch','run_tests','read_source_file')]
HYBRID_TOOLS += [{'type':'function','function':{'name':n,'description':d,'parameters':s.model_json_schema()}} for n,(s,d) in EXTRA.items()]
