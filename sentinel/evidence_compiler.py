"""V4: typed observations, whole-object selection, explicit provenance and omissions.

This module cannot access the experiment registry or infer a diagnosis. Scores are
selection heuristics, not calibrated probabilities. Raw evidence stays immutable.
"""
import ast
from collections import Counter, defaultdict
import json
import math
import re
from urllib.parse import urlsplit
from .context_engineering import SOURCE_KIND, critical_path


def size(value):
    return len(json.dumps(value, ensure_ascii=False, default=str))


def finite(value):
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None


def logs(rows):
    clusters = {}
    for row in rows:
        message = str(row.get('error') or row.get('message') or '')
        template = re.sub(r'\b[0-9a-f]{16,}\b|\b\d+(?:\.\d+)?\b', '<value>', message)
        severity = row.get('severity') or ('ERROR' if (row.get('status') or 0) >= 500 else 'INFO')
        key = (row.get('service'), severity, row.get('path'), row.get('status'), template)
        seen = str(row.get('ts', 'unknown'))
        cluster = clusters.setdefault(key, dict(service=key[0], severity=severity,
            path=key[2], status=key[3], template=template, count=0,
            first_seen=seen, last_seen=seen, representative=dict(row),
            anomaly_score=1 if severity == 'ERROR' else 0))
        cluster['count'] += 1
        cluster['first_seen'] = min(cluster['first_seen'], seen)
        cluster['last_seen'] = max(cluster['last_seen'], seen)
    ranked = sorted(clusters.values(), key=lambda r: (r['anomaly_score'], r['count']), reverse=True)
    return {'clusters': ranked[:8], 'sampled_rows': len(rows),
            'omitted_clusters': max(0, len(ranked)-8), 'count_scope': 'queried sample only'}


def metrics(payload):
    result = []
    for row in payload.get('metric_windows', []):
        values = [finite(v) for v in row.get('values', [])]
        known = [v for v in values if v is not None]
        current = values[-1] if values else None
        baseline = finite(row.get('baseline'))
        delta = current-baseline if current is not None and baseline is not None else None
        times = row.get('timestamps', [])
        result.append({'service': row['service'], 'name': row['metric'], 'baseline': baseline,
            'current': current, 'peak': max(known) if known else None, 'delta': delta,
            'trend': 'unknown' if len(values)<2 or values[0] is None or current is None else
                'increasing' if current>values[0] else 'decreasing' if current<values[0] else 'stable',
            'anomaly_score': abs(delta)/max(abs(baseline), .001) if delta is not None else None,
            'window': {'start': times[0] if times else None, 'end': times[-1] if times else None,
                       'baseline_at': row.get('baseline_at'), 'baseline_health': row.get('baseline_health', 'unknown')},
            'anomaly_definition': 'absolute relative change; baseline is not known healthy'})
    result.sort(key=lambda r:(r['anomaly_score'] or 0,r['current'] or 0),reverse=True)
    return {'metrics': result, 'http': payload.get('http', []),
            'http_window_seconds': payload.get('http_window_seconds')}


def traces(payload):
    result = []
    for trace in payload[:3]:
        spans = []; calls = defaultdict(list); edges = set()
        for span in trace.get('spans', []):
            tags = {t['key']: t.get('value') for t in span.get('tags', [])}
            service = trace.get('processes', {}).get(span.get('processID'), {}).get('serviceName', 'unknown')
            item = {'span_id': span.get('spanID'), 'service': service, 'operation': span.get('operation'),
                    'duration_ms': span.get('duration_us', 0)/1000,
                    'error': bool(tags.get('error') or tags.get('otel.status_code') == 'ERROR'),
                    'parent_refs': span.get('references', [])}
            if tags.get('http.status_code') is not None: item['http_status'] = tags['http.status_code']
            if tags.get('db.statement'): item['sql'] = tags['db.statement']
            spans.append(item)
            if tags.get('span.kind') != 'client': continue
            endpoint = tags.get('http.url')
            sql = tags.get('db.statement')
            target = urlsplit(endpoint).hostname if endpoint else tags.get('db.system') or tags.get('net.peer.name')
            if target: edges.add((service, target))
            if endpoint or sql:
                calls[(service, 'sql' if sql else 'http', sql or endpoint)].append(span)
        repeated = []
        for (service, kind, operation), group in calls.items():
            if len(group)<2: continue
            times = sorted(s['startTime'] for s in group if s.get('startTime') is not None)
            repeated.append({'caller': service, 'kind': kind, 'operation': operation, 'count': len(group),
                'total_client_duration_ms': sum(s.get('duration_us', 0) for s in group)/1000,
                'start_intervals_ms': [(b-a)/1000 for a,b in zip(times,times[1:])][:12],
                'intervals_omitted': max(0,len(times)-13)})
        errors = [s for s in spans if s['error']]
        result.append({'trace_id': trace.get('traceID'), 'span_count': len(spans),
            'critical_path': critical_path(spans), 'error_spans': errors[:6],
            'error_spans_omitted': max(0,len(errors)-6),
            'slow_spans': sorted(spans, key=lambda s:s['duration_ms'], reverse=True)[:5],
            'service_path': [list(e) for e in sorted(edges)],
            'fanout': dict(Counter(a for a,b in edges)), 'repeated_calls': repeated,
            'count_scope': 'client spans only; SQL counts do not include enclosing internal spans',
            'detail_tool': {'name':'get_trace_detail', 'arguments':{'trace_id':trace.get('traceID')}}})
    return result


def code(payload):
    """Only report actual shown lines; infer AST relationships within this slice only."""
    lines = payload.get('source', '').splitlines()
    # read_source adds numbered prefixes; remove them only for parsing.
    plain = '\n'.join(re.sub(r'^\d+: ', '', line) for line in lines)
    symbols = []; callers = []; callees = set()
    try:
        tree = ast.parse(plain)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append(node.name)
                called = sorted({n.func.id if isinstance(n.func, ast.Name) else n.func.attr
                    for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))})
                callees.update(called)
                callers.extend({'caller':node.name,'callee':name} for name in called)
    except SyntaxError: pass  # A real partial source slice may not be an AST module.
    # Default code preview contains complete lines, bounded separately from detail.
    shown = lines[:45]
    start = payload.get('start_line', 1)
    return {'file':payload.get('path'), 'symbol':symbols, 'line_range':[start,start+len(shown)-1],
        'snippet':'\n'.join(shown), 'callers':callers, 'callees':sorted(callees),
        'relationship_scope':'parsed source slice only; not whole repository callers',
        'omitted_lines':len(lines)-len(shown), 'detail_tool':'read_source_file'}


def _compile(kind, payload):
    if kind=='search_logs': return logs(payload)
    if kind=='query_metrics': return metrics(payload)
    if kind in ('get_trace','get_trace_detail'): return traces(payload)
    if kind in ('get_code_symbol','get_code_context','read_source_file'): return code(payload)
    if kind=='inspect_database':
        activity = payload.get('activity', [])
        return {'connections':dict(Counter(r.get('application_name','unknown') for r in activity)),
            'connection_scope':'sample of observed application sessions, capped at 30',
            'active_sessions':[r for r in activity if r.get('state')=='active'],
            'pool':payload.get('pool'), 'pool_note':'pool state is separately observed by get_service_health',
            'locks':payload.get('locks'), 'slow_queries':payload.get('slow_queries'),
            'query_fingerprint':[{'queryid':r.get('queryid'),'sql':r.get('query'),'calls_delta':r.get('calls_delta')}
                                 for r in payload.get('call_deltas',[])],
            'cumulative_statements':payload.get('statements',[]),
            'sample_seconds':payload.get('sample_seconds'), 'window':payload.get('window'),
            'cumulative_note':'lifetime calls/mean_exec_time cannot establish current causality; compare deltas'}
    if kind=='get_service_health':
        return [{'service':r['service'], 'health':r.get('health'),
                 'pool':r.get('pool-stats',{}).get('body',{}).get('pool',{}),
                 'pool_scope':'requests_errors/queued/wait_ms cumulative; waiting/available instantaneous'} for r in payload]
    return payload


def compile_observation(kind,payload,max_chars=2800):
    """Bound collections by dropping complete trailing objects, never string fragments."""
    from copy import deepcopy
    result=deepcopy(_compile(kind,payload));omissions=[]
    # These keys describe ordered collections, not atomic tuples (line ranges,
    # graph edges, span references), so dropping one entry retains valid objects.
    collections={'clusters','metrics','http','slow_spans','error_spans','repeated_calls',
                 'active_sessions','locks','slow_queries','query_fingerprint','cumulative_statements'}
    def candidates(value,path=()):
        found=[]
        if isinstance(value,list) and len(value)>1 and (not path or path[-1] in collections):
            found.append((size(value),value,path))
        if isinstance(value,dict):
            for key,child in value.items(): found.extend(candidates(child,path+(key,)))
        elif isinstance(value,list):
            for index,child in enumerate(value): found.extend(candidates(child,path+(index,)))
        return found
    while size(result)>max_chars:
        choices=candidates(result)
        if not choices: break
        _,collection,path=max(choices,key=lambda c:c[0]);collection.pop()
        existing=next((o for o in omissions if o['path']==list(path)),None)
        if existing: existing['omitted_objects']+=1
        else: omissions.append({'path':list(path),'omitted_objects':1})
    # Preserve normal payload shape, with explicit omission metadata when needed.
    if omissions:
        return {'summary':result,'collection_omissions':omissions,'raw_detail':'read_evidence; complete stored payload'}
    return result


def compile_pack(evidence, max_chars=14000, services=(), pinned_ids=()):
    candidates = []; families = Counter(SOURCE_KIND.get(e['kind'],e['kind']) for e in evidence)
    raw_size = sum(size(e['payload']) for e in evidence)
    for index, e in enumerate(evidence):
        # Control data already has dedicated fields in InvestigationState.
        if e['kind'] in ('run_deterministic_triage','get_service_topology','submit_root_cause_decision','validate_patch','run_tests'): continue
        family = SOURCE_KIND.get(e['kind'],e['kind'])
        observation = compile_observation(e['kind'],e['payload'])
        text = json.dumps(observation,ensure_ascii=False,default=str)
        related = [s for s in services if s in text]
        anomaly = bool(re.search(r'Timeout|TypeError|"error": true|"status": 50|PgSleep',text))
        components = {'directness':2 if family in ('trace','database','code') else 1,
            'anomaly':2*int(anomaly), 'hypothesis_relevance':2*bool(related),
            'source_uniqueness':1/max(families[family],1),
            'cross_source_support':len({SOURCE_KIND.get(x['kind'],x['kind']) for x in evidence
                if related and any(s in json.dumps(x['payload'],default=str) for s in related)})/5,
            'recency':index/max(len(evidence),1)}
        item = {'id':e['id'],'kind':e['kind'],'collected_at':str(e.get('collected_at','unknown')),
            'observations':observation,'raw_retrieval':'read_evidence', 'representation':'compiled',
            'importance':components,'importance_score':sum(components.values())}
        candidates.append((item,family))
    candidates.sort(key=lambda c:(c[0]['id'] in pinned_ids,c[0]['importance_score']), reverse=True)
    selected = []; omitted = []; seen = set(); counts = Counter(); chosen = set()
    def add(item,family):
        identity = (item['kind'],json.dumps(item['observations'],sort_keys=True,default=str))
        if identity in seen:
            omitted.append({'id':item['id'],'reason':'duplicate_complete_observation'}); return False
        if size(selected+[item])>max_chars:
            omitted.append({'id':item['id'],'reason':'whole_object_exceeds_remaining_budget'}); return False
        selected.append(item); seen.add(identity); counts[family]+=1; chosen.add(item['id']); return True
    # One per source family before admitting repeats: diversity is not an afterthought.
    visited = set()
    for item,family in candidates:
        if family not in visited:
            if add(item,family): visited.add(family)
    considered = {x['id'] for x in omitted}|chosen
    for item,family in candidates:
        if item['id'] in considered: continue
        if counts[family]>=3: omitted.append({'id':item['id'],'reason':'source_family_cap'}); continue
        add(item,family)
    for e in evidence:
        if e['id'] not in chosen and not any(x['id']==e['id'] for x in omitted):
            omitted.append({'id':e['id'],'reason':'available_in_control_context'})
    packed = {'items':selected,'budget_chars':max_chars,'omitted_items':len(omitted),
        'raw_estimated_tokens':(raw_size+3)//4,'compressed_estimated_tokens':(size(selected)+3)//4,
        'estimate_method':'characters / 4; never provider usage','source_families':sorted(counts)}
    telemetry = {'raw_context_size':raw_size,'compiled_context_size':size(selected),
        'compression_ratio':size(selected)/raw_size if raw_size else None,
        'ratio_definition':'compiled/raw evidence payload characters; lower means smaller, not better accuracy',
        'evidence_dropped':omitted,'evidence_retained':[i['id'] for i in selected],
        'diversity_families':sorted(counts),'pinned_evidence_ids':list(pinned_ids),
        'pinned_context_size':None,'provider_input_tokens':None}
    return packed,telemetry
