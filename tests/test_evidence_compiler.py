"""V4 boundaries: deterministic fixture tests, not RCA or live benchmark scores."""
import asyncio
from copy import deepcopy
import json
import pytest
from sentinel.evidence_compiler import logs,metrics,traces,code,compile_pack,compile_observation,size
from sentinel.context_delivery import raw_evidence_page,visible_reads,detail_page
from sentinel.infra_observations import rate
from sentinel.runtime_state import InvestigationState
from sentinel.runtime_tools import tools_for,schema_for,EvidencePage

def evidence(kind,payload,n=0):
    return {'id':'E-'+format(n,'016x'),'kind':kind,'payload':payload}

def test_five_thousand_log_duplicates_form_one_cluster_with_actual_representative():
    rows=[{'service':'order-service','status':500,'error':f'failed request {i}', 'ts':f'{i:05d}'} for i in range(5000)]
    summary=logs(rows)
    assert len(summary['clusters'])==1 and summary['clusters'][0]['count']==5000
    assert summary['clusters'][0]['representative']==rows[0]
    assert summary['clusters'][0]['first_seen']=='00000' and summary['clusters'][0]['last_seen']=='04999'

def test_log_severity_and_service_do_not_merge():
    rows=[{'service':s,'status':status,'error':'timeout'} for s in ('order-service','payment-service') for status in (200,500)]
    assert len(logs(rows)['clusters'])==4

def test_metric_no_baseline_is_unknown_not_healthy_zero():
    result=metrics({'metric_windows':[{'service':'inventory-service','metric':'db_qps','values':[4,8], 'timestamps':[100,120]}]})['metrics'][0]
    assert result['baseline'] is None and result['delta'] is None and result['anomaly_score'] is None
    assert result['window']['start']==100 and result['window']['end']==120 and result['trend']=='increasing'
    assert 'values' not in result and result['peak']==8

def test_nonfinite_metric_samples_are_not_claimed_numeric():
    result=metrics({'metric_windows':[{'service':'inventory-service','metric':'db_qps','baseline':float('nan'),'values':[2,float('inf')]}]})['metrics'][0]
    assert result['current'] is None and result['trend']=='unknown'
    json.dumps(result,allow_nan=False)

def trace_fixture():
    sql='SELECT id,name,price,stock FROM products WHERE id=%s'
    def span(i,kind):
        return {'spanID':str(i),'processID':'p1','operation':'SELECT products','duration_us':52,
            'startTime':100+i*100,'tags':[{'key':'span.kind','value':kind},{'key':'db.statement','value':sql},{'key':'db.system','value':'postgresql'}]}
    return {'traceID':'a'*32,'processes':{'p1':{'serviceName':'inventory-service'}},
            'spans':[span(i,'client') for i in range(20)]+[span(100,'internal')]}

def test_sql_fanout_counts_only_client_spans_and_retains_complete_sql():
    result=traces([trace_fixture()])[0]
    assert result['repeated_calls'][0]['count']==20
    assert result['repeated_calls'][0]['operation']=='SELECT id,name,price,stock FROM products WHERE id=%s'
    assert result['fanout']=={'inventory-service':1}

def test_trace_detail_is_unmodified_raw_spans():
    raw=trace_fixture();page=detail_page([raw],3,5)[0]
    assert page['spans']==raw['spans'][3:8] and page['pagination']['next_offset']==8

def test_compiled_code_citation_covers_only_shown_complete_lines():
    source={'path':'services/runtime.py','start_line':10,'end_line':89,'source':'\n'.join(f'{i}: value_{i} = {i}' for i in range(10,90))}
    summary=code(source)
    assert summary['line_range']==[10,54] and summary['omitted_lines']==35
    shown={'evidence':{'items':[{'id':'E-code','kind':'read_source_file','observations':summary}]}}
    assert visible_reads(shown,'provider-test')['E-code']['end_line']==54

def test_ast_code_context_reports_real_calls_not_invented_callers():
    result=code({'path':'services/pricing.py','start_line':1,'source':'1: def total(x):\n2:     return round(float(x), 2)'})
    assert result['symbol']==['total'] and result['callees']==['float','round']

def test_importance_and_diversity_prevent_log_monopoly():
    rows=[evidence('search_logs',[{'service':'inventory-service','error':f'Timeout kind_{i}','status':500}],i) for i in range(15)]
    rows += [evidence('inspect_database',{'activity':[],'call_deltas':[{'queryid':1,'query':'SELECT * FROM products','calls_delta':80}]},50)]
    pack,telemetry=compile_pack(rows,8000,['inventory-service'])
    assert {'logs','database'}<=set(telemetry['diversity_families'])
    assert sum(i['kind']=='search_logs' for i in pack['items'])<=3
    assert all(set(i['importance'])=={'directness','anomaly','hypothesis_relevance','source_uniqueness','cross_source_support','recency'} for i in pack['items'])

def test_no_partial_sql_or_json_when_atomic_item_too_large():
    sql='SELECT '+','.join('col'+str(i) for i in range(4000))+' FROM products'
    pack,telemetry=compile_pack([evidence('inspect_database',{'call_deltas':[{'query':sql}]})],1000)
    assert not pack['items'] and telemetry['evidence_dropped'][0]['reason']=='whole_object_exceeds_remaining_budget'

def test_pinned_control_survives_compiler_and_rebuild():
    s=InvestigationState(run_id='run',incident_id='incident',version='4')
    s.critical_evidence={'E-pin':{'kind':'search_logs','observations':{'error':'TypeError'}}}
    s.validation_errors={'repair':{'message':'read missing line'}}
    pack,_=compile_pack([evidence('search_logs',[{'error':'normal'}])],1000)
    rebuilt=s.rebuild(pack)
    assert rebuilt['P1']['critical_evidence']==s.critical_evidence
    assert rebuilt['P0']['validation_errors']==s.validation_errors

def test_compiler_does_not_mutate_raw_evidence():
    rows=[evidence('get_trace',[trace_fixture()]*3)];before=deepcopy(rows)
    compile_pack(rows)
    assert rows==before

def test_large_collection_omissions_are_explicit_complete_objects():
    raw=[{'service':'s','status':500,'error':f'error_{chr(65+i)} '+'x'*600} for i in range(8)]
    result=compile_observation('search_logs',raw)
    assert result['collection_omissions'] and result['summary']['clusters'][0]['representative']==raw[0]

def test_raw_evidence_pages_can_reconstruct_full_payload_without_string_cuts():
    raw={'rows':[{'sql':f'SELECT {i} '+'x'*600,'duration':i} for i in range(35)]}
    result={};offset=0;pages=0
    while True:
        page=raw_evidence_page(raw,offset,4);pages+=1
        for record in page['records']: result[tuple(record['path'])]=record['value']
        if page['next_offset'] is None: break
        offset=page['next_offset']
    assert pages>1 and [result[('rows',i)] for i in range(35)]==raw['rows']

def test_raw_evidence_oversized_atomic_string_fails_explicitly():
    with pytest.raises(ValueError,match='DETAIL_OBJECT_TOO_LARGE'): raw_evidence_page({'sql':'x'*9000})

@pytest.mark.parametrize('before,after,seconds,expected',[(10,15,2,2.5),(10,5,2,None),(None,5,2,None),(1,2,0,None)])
def test_counter_resets_missing_offsets_and_invalid_windows_are_unknown(before,after,seconds,expected):
    assert rate(before,after,seconds)==expected

def test_v4_detail_schema_changes_only_v4_and_repair_uses_same_schema():
    s=InvestigationState(run_id='r',incident_id='i',version='4')
    tool=tools_for({'read_evidence'},s)[0]
    assert tool['function']['parameters']==EvidencePage.model_json_schema()
    assert schema_for(s,'read_evidence') is EvidencePage
    s.version='3.1.4';assert schema_for(s,'read_evidence') is not EvidencePage

def test_telemetry_measures_actual_payloads_and_does_not_invent_provider_usage():
    rows=[evidence('search_logs',[{'error':'failure','status':500}]*50)]
    pack,telemetry=compile_pack(rows)
    assert telemetry['raw_context_size']==size(rows[0]['payload'])
    assert telemetry['compiled_context_size']==size(pack['items'])
    assert telemetry['compression_ratio']==size(pack['items'])/size(rows[0]['payload'])
    assert telemetry['provider_input_tokens'] is None
