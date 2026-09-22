"""Bounded, deterministic evidence summaries; raw evidence remains in PostgreSQL."""
import json
import re
from collections import Counter


SOURCE_KIND = {'search_logs':'logs','query_metrics':'metrics','inspect_database':'database',
               'inspect_redis':'cache','inspect_kafka':'queue','get_service_health':'health',
               'get_trace':'trace','get_trace_detail':'trace','read_source_file':'code',
               'get_code_symbol':'code','get_code_context':'code'}


def independent_sources(ids, evidence):
    return sorted({SOURCE_KIND[e['kind']] for e in evidence
                   if e['id'] in ids and e['kind'] in SOURCE_KIND})


def log_summary(rows, limit=8):
    groups={}
    for row in rows:
        error=str(row.get('error') or '')
        template=re.sub(r'\b[0-9a-f]{16,}\b|\b\d+(?:\.\d+)?\b','<value>',error)
        key=(row.get('service'),row.get('path'),row.get('status'),template)
        item=groups.setdefault(key,{'service':key[0],'path':key[1],'status':key[2],
            'severity':'ERROR' if (key[2] or 0)>=500 else 'INFO','template':template,
            'count':0,'first_seen':str(row.get('ts')),'last_seen':str(row.get('ts')),
            'example_trace_id':row.get('trace_id')})
        item['count']+=1
        item['first_seen']=min(item['first_seen'],str(row.get('ts')))
        item['last_seen']=max(item['last_seen'],str(row.get('ts')))
    ranked=sorted(groups.values(),key=lambda x:(x['severity']=='ERROR',x['count']),reverse=True)
    return {'sampled_rows':len(rows),'groups':ranked[:limit],'omitted_groups':max(0,len(ranked)-limit),
            'count_scope':'queried sample, not total incident log volume'}


def trace_summary(traces, limit=3):
    output=[]
    for trace in traces[:limit]:
        spans=[];edges=set();repeats=Counter();starts={}
        processes=trace.get('processes',{})
        for span in trace.get('spans',[]):
            tags={t['key']:t.get('value') for t in span.get('tags',[])}
            service=processes.get(span.get('processID'),{}).get('serviceName','unknown')
            url=tags.get('http.url','');peer=tags.get('net.peer.name')
            if url.startswith('http://'):
                from urllib.parse import urlsplit
                peer=urlsplit(url).hostname
            if peer and peer!=service: edges.add((service,peer))
            # Count client spans only; server/internal ASGI spans are not retries.
            if tags.get('span.kind')=='client' and url:
                key=(service,url);repeats[key]+=1
                if span.get('startTime') is not None: starts.setdefault(key,[]).append(span['startTime'])
            spans.append({'span_id':span.get('spanID'),'service':service,'operation':span['operation'],
                          'duration_ms':span['duration_us']/1000,'error':bool(tags.get('error') or tags.get('otel.status_code')=='ERROR'),
                          'http_status':tags.get('http.status_code'),'parent_refs':span.get('references',[])})
        output.append({'trace_id':trace['traceID'],'span_count':len(spans),
            'critical_path':critical_path(spans),
            'slowest_spans':sorted(spans,key=lambda s:s['duration_ms'],reverse=True)[:5],
            'error_spans':[s for s in spans if s['error']][:6],
            'cross_service_dependencies':[list(e) for e in sorted(edges)],
            'repeated_calls':[{'caller':k[0],'endpoint':k[1],'count':n,
                'start_intervals_ms':[(b-a)/1000 for a,b in zip(sorted(starts.get(k,[])),sorted(starts.get(k,[]))[1:])]}
                for k,n in repeats.items() if n>1],
            'fan_out':dict(Counter(a for a,b in edges)),
            'critical_path_note':'slowest spans and parent references retained; durations overlap and must not be summed'})
    return output


def critical_path(spans):
    by_id={s['span_id']:s for s in spans if s['span_id']};children={}
    for span in spans:
        for ref in span['parent_refs']:
            if ref.get('refType')=='CHILD_OF' and ref.get('spanID') in by_id:
                children.setdefault(ref['spanID'],[]).append(span)
    if not spans: return []
    node=max(spans,key=lambda s:s['duration_ms']);path=[];seen=set()
    while node and node['span_id'] not in seen:
        seen.add(node['span_id']);path.append({k:node[k] for k in ('span_id','service','operation','duration_ms','error')})
        node=max(children.get(node['span_id'],[]),key=lambda s:s['duration_ms'],default=None)
    return {'method':'longest nested span chain approximation, not sum of overlapping durations','spans':path}


def metric_summary(payload):
    # Baselines must come from a measured historical window, never an invented default.
    rows=[]
    for series in payload.get('metric_windows',[]):
        values=series.get('values',[]);baseline=series.get('baseline');current=values[-1] if values else None
        delta=current-baseline if current is not None and baseline is not None else None
        rows.append({'service':series['service'],'metric':series['metric'],'baseline':baseline,
            'current':current,'delta':delta,'peak':max(values) if values else None,
            'trend':'unknown' if len(values)<2 else ('increasing' if values[-1]>values[0] else 'decreasing' if values[-1]<values[0] else 'stable'),
            'anomaly_score':abs(delta)/max(abs(baseline),.001) if delta is not None else None,
            'anomaly_score_definition':'absolute relative change, not calibrated probability'})
    return {'http_window_seconds':payload.get('http_window_seconds'),'http':payload.get('http',[]),
            'metric_summary':rows,'missing_baseline':'unknown; pre-incident does not guarantee healthy'}


def summarize(kind,payload):
    if kind=='get_service_health':
        return [{'service':r['service'],'health':r.get('health'),
            'current_pool':{k:v for k,v in r.get('pool-stats',{}).get('body',{}).get('pool',{}).items() if k in ('pool_size','pool_available','pool_max','requests_waiting')},
            'cumulative_pool':{k:v for k,v in r.get('pool-stats',{}).get('body',{}).get('pool',{}).items() if k in ('requests_errors','requests_queued','requests_wait_ms')},
            'note':'Cumulative values are not current pressure; waiting/available are instantaneous.'} for r in payload]
    if kind=='search_logs': return log_summary(payload)
    if kind in ('get_trace','get_trace_detail'): return trace_summary(payload)
    if kind=='query_metrics': return metric_summary(payload)
    if kind=='inspect_database':
        return {**{k:v for k,v in payload.items() if k not in ('activity','statements')},
                'active_sessions':[s for s in payload.get('activity',[]) if s.get('state')=='active'],
                'call_deltas':payload.get('call_deltas',[]),
                'cumulative_statements_omitted':True}
    return payload


def evidence_pack(evidence, max_chars=16000, services=()):
    ranked=[];seen=set();raw_chars=0
    for index,item in enumerate(evidence):
        payload=item['payload'];raw=json.dumps(payload,ensure_ascii=False,default=str);raw_chars+=len(raw)
        summary=summarize(item['kind'],payload);text=json.dumps(summary,ensure_ascii=False,default=str)
        identity=(item['kind'],text)
        if identity in seen: continue
        seen.add(identity)
        score=3 if item['kind'] in ('get_code_symbol','get_code_context','read_source_file') else 0
        score+=4*bool(re.search(r'Timeout|TypeError|"error": true|"status": 50',text))
        score+=2*any(s in text for s in services)
        score+=int(item['kind'] in ('inspect_database','inspect_kafka','inspect_redis'))
        ranked.append((score+index/max(len(evidence),1),item,summary,text))
    # Recent values break ties so an evolving incident is not frozen at its initial snapshot.
    ranked.sort(key=lambda x:x[0],reverse=True)
    result=[];used=0;counts=Counter()
    for score,item,summary,text in ranked:
        family=SOURCE_KIND.get(item['kind'],item['kind'])
        if len(result)>=16 or counts[family]>=(3 if family in ('trace','code') else 4): continue
        remaining=max_chars-used
        if remaining<300: break
        cap=min(3200,remaining-180)
        result.append({'id':item['id'],'kind':item['kind'],'collected_at':str(item.get('collected_at','unknown')),'observations':summary if len(text)<=cap else text[:cap],
                       'truncated':len(text)>cap,'raw_retrieval':'read_evidence'})
        used+=len(json.dumps(result[-1],ensure_ascii=False));counts[family]+=1
    return {'items':result,'budget_chars':max_chars,'raw_estimated_tokens':(raw_chars+3)//4,
            'compressed_estimated_tokens':(used+3)//4,'estimate_method':'characters / 4; not provider usage',
            'omitted_items':len(evidence)-len(result)}


def tool_efficiency(calls):
    """Retrospective heuristic, identical rubric across versions; not human usefulness labels."""
    seen=set();rows=[]
    for call in calls:
        key=(call['agent'],call['tool_name'],json.dumps(call.get('arguments'),sort_keys=True))
        status='failed_tool_call' if call.get('status')!='succeeded' else 'redundant_tool_call' if key in seen else 'useful_tool_call'
        reason='execution failed' if status=='failed_tool_call' else 'same role/tool/arguments previously queried; time-dependent refresh may still be useful' if status=='redundant_tool_call' else 'first successful query; relevance not independently adjudicated'
        seen.add(key);rows.append({'id':str(call['id']),'classification':status,'reason':reason})
    counts=Counter(r['classification'] for r in rows)
    return {'rubric':'exact duplicate role/tool/arguments within run; conservative proxy, not semantic utility',
            **dict(counts),'total':len(rows),'useful_rate':counts['useful_tool_call']/len(rows) if rows else None,'calls':rows}
