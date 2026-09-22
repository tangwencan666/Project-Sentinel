"""Operator-side fixture evidence audit; never imported or exposed to an Investigator."""
import json
from pathlib import Path
from phase3_dataset import dataset_path

ROOT=Path(__file__).resolve().parents[1]


def audit(row):
    evidence=row.get('ledger',{}).get('evidence',[])
    http={h['service']:h for h in row.get('measured',{}).get('fault_active',{}).get('http',[])}
    def h(service,key): return float(http.get(service,{}).get(key) or 0)
    def source(kind): return [e for e in evidence if e['kind']==kind]
    def db_deltas(fragment):
        return [(e['id'],d['calls_delta']) for e in source('inspect_database') for d in e['payload'].get('call_deltas',[]) if fragment in d.get('query','') and d.get('calls_delta') is not None]
    scenario=row['scenario'];ids=[];facts={};passed=False
    if scenario=='slow_query':
        ids=[e['id'] for e in source('inspect_database') if any(a.get('state')=='active' and 'pg_sleep(1.2)' in a.get('query','') for a in e['payload'].get('activity',[]))]
        facts={'inventory_p95_ms':h('inventory-service','p95_ms'),'active_sleep_evidence_ids':ids};passed=bool(ids) and facts['inventory_p95_ms']>=1000
    elif scenario=='pool_exhaustion':
        observations=[(e['id'],sum(a.get('state')=='active' and a.get('application_name')=='inventory-service' and 'pg_sleep' in a.get('query','') for a in e['payload'].get('activity',[]))) for e in source('inspect_database')]
        ids=[i for i,n in observations if n>=3];facts={'active_sleep_observations':observations,'inventory_error_pct':h('inventory-service','error_pct')};passed=bool(ids) and facts['inventory_error_pct']>0
    elif scenario=='n_plus_one':
        observations=[]
        for e in evidence:
            if e['kind'] not in ('get_trace','get_trace_detail'): continue
            for trace in e['payload']:
                count=sum(any(t.get('key')=='db.statement' and 'FROM products WHERE id=' in str(t.get('value')) for t in span.get('tags',[])) for span in trace.get('spans',[]))
                if count:observations.append({'evidence_id':e['id'],'trace_id':trace['traceID'],'product_point_queries':count})
        ids=[o['evidence_id'] for o in observations if o['product_point_queries']>=10]
        facts={'trace_query_counts':observations,'statement_call_deltas':db_deltas('FROM products WHERE id=')};passed=bool(ids)
    elif scenario=='cache_miss':
        ids=[e['id'] for e in source('inspect_redis') if e['payload'].get('catalog_ttl')==-2]
        deltas=db_deltas('FROM products ORDER BY id')
        facts={'missing_catalog_evidence_ids':ids,'product_query_deltas':deltas};passed=bool(ids) and any(n>=2 for _,n in deltas)
    elif scenario=='consumer_lag':
        samples=[{'id':e['id'],'at':e['collected_at'],'partitions':e['payload']} for e in source('inspect_kafka')]
        growth=[]
        for before,after in zip(samples,samples[1:]):
            by_partition={p['partition']:p for p in before['partitions']}
            for b in after['partitions']:
                a=by_partition.get(b['partition'])
                if a and b.get('lag') is not None and a.get('lag') is not None and b['lag']>a['lag'] and b.get('committed_offset')==a.get('committed_offset') and b.get('end_offset',0)>a.get('end_offset',0):growth.append([before['id'],after['id'],a['lag'],b['lag']])
        facts={'growing_lag_with_static_commits':growth};passed=bool(growth)
    elif scenario=='downstream_timeout':
        facts={'payment_p95_ms':h('payment-service','p95_ms'),'order_error_pct':h('order-service','error_pct')};passed=facts['payment_p95_ms']>=2900 and facts['order_error_pct']>0
    elif scenario=='retry_storm':
        calls=h('payment-service','requests');orders=h('order-service','requests')
        facts={'payment_calls':calls,'order_calls':orders,'amplification':calls/orders if orders else None,'payment_error_pct':h('payment-service','error_pct')};passed=orders>0 and calls/orders>=4 and facts['payment_error_pct']>0
    elif scenario=='code_exception':
        ids=[e['id'] for e in source('search_logs') if any('TypeError' in str(log.get('error')) for log in e['payload'])]
        facts={'type_error_evidence_ids':ids,'order_error_pct':h('order-service','error_pct')};passed=bool(ids) and facts['order_error_pct']>0
    return {'scenario':scenario,'incident_id':row['incident_id'],'fault_effect_observed':passed,'facts':facts}


def main():
    versions={v:[audit(r) for r in json.loads(dataset_path(v).read_text(encoding='utf-8'))['results']] for v in ('v2','v3')}
    result={'scope':'Post-run operator-side validity audit, distinct from model correctness. Original invalid pool trials remain saved.',
            'versions':versions,'all_eight_per_version_observed':all(len(rows)==8 and all(r['fault_effect_observed'] for r in rows) for rows in versions.values())}
    (ROOT/'evaluation/fault-validity.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':result['all_eight_per_version_observed'],'rows':{v:[{'scenario':r['scenario'],'observed':r['fault_effect_observed']} for r in rows] for v,rows in versions.items()}}))
    if not result['all_eight_per_version_observed']:raise SystemExit(1)


if __name__=='__main__':main()
