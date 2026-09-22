"""Synthetic boundary tests are not accuracy/evaluation evidence."""
import asyncio
import ast
import json
import uuid
from pathlib import Path
import pytest
from sentinel.context_engineering import independent_sources,log_summary,trace_summary,evidence_pack,metric_summary,tool_efficiency
from sentinel.hybrid_tools import derive_signals,topology_from_traces,code_symbol,RootCauseDecision
from sentinel.verification import deterministic_verify,combine_verdict,patch_risk


def test_triage_requires_measurements_and_is_advisory():
    empty=derive_signals({});assert empty['signals']==[] and empty['advisory_only']
    signals=derive_signals({'inspect_redis':{'data':{'catalog_ttl':-2},'ids':['cache']},
        'inspect_database':{'data':{'call_deltas':[{'query':'SELECT * FROM products','calls_delta':9}]},'ids':['db']}})
    assert signals['signals'][0]['evidence_ids']==['cache','db']
    assert 'category' not in signals['signals'][0]


def test_queue_growth_uses_offsets_not_http_errors():
    obs={'queue_before':{'ids':['before'],'data':[{'partition':0,'end_offset':100,'committed_offset':80,'lag':20}]},
         'inspect_kafka':{'ids':['after'],'data':[{'partition':0,'end_offset':120,'committed_offset':80,'lag':40}]},'queue_sample_seconds':5}
    s=derive_signals(obs)['signals'][0]
    assert s['observations'][0]['producer_rps']==4 and s['observations'][0]['consumer_rps']==0
    assert s['suspected_services']==['notification-service']


def test_evidence_aliases_do_not_count_as_independent():
    e=[{'id':'1','kind':'get_trace'},{'id':'2','kind':'get_trace_detail'},{'id':'3','kind':'run_deterministic_triage'}]
    assert independent_sources(['1','2','3'],e)==['trace']


def test_log_clustering_retains_sample_count_and_times():
    rows=[{'service':'s','path':'/x','status':500,'error':'Timeout 1','ts':'a'},
          {'service':'s','path':'/x','status':500,'error':'Timeout 2','ts':'b'}]
    item=log_summary(rows)['groups'][0]
    assert item['count']==2 and item['first_seen']=='a' and item['last_seen']=='b'


def test_metrics_unknown_baseline_stays_unknown():
    r=metric_summary({'metric_windows':[{'service':'s','metric':'qps','baseline':None,'values':[1,3]}]})['metric_summary'][0]
    assert r['anomaly_score'] is None and r['delta'] is None and r['peak']==3 and r['trend']=='increasing'


def test_trace_repeat_counts_clients_only():
    trace={'traceID':'t','processes':{'p':{'serviceName':'order-service'}},'spans':[
        {'spanID':str(i),'operation':'POST','processID':'p','duration_us':1000,'startTime':i*2000,'tags':[
        {'key':'span.kind','value':kind},{'key':'http.url','value':'http://payment-service:8000/charge'}]}
        for i,kind in enumerate(['client','server','client'])]}
    r=trace_summary([trace])[0]['repeated_calls'][0]
    assert r['count']==2 and r['start_intervals_ms']==[4]
    assert topology_from_traces([trace])['edges'][0]['target']=='payment-service'


def test_compression_preserves_raw_and_bounds_items():
    e=[{'id':str(i),'kind':'search_logs','payload':[{'service':'s','status':500,'error':'Timeout '+str(i),'ts':'now'}]*50} for i in range(30)]
    original=json.dumps(e)
    result=evidence_pack(e,3000)
    assert len(result['items'])<=4 and result['compressed_estimated_tokens']<result['raw_estimated_tokens']
    assert json.dumps(e)==original and result['omitted_items']>0


@pytest.mark.parametrize('path',['services/app.py','sentinel/scenarios.py','../.env'])
def test_symbol_does_not_expand_source_privilege(path):
    with pytest.raises(ValueError): code_symbol(path,'total')


def test_symbol_matches_real_numbered_source():
    result=code_symbol('services/pricing.py','total')
    assert result['start_line']==3 and result['source'].startswith('3: def total')


def test_deterministic_failure_blocks_llm_verified():
    decision={'supporting_evidence':['a'],'affected_service':'notification-service','category':'UNKNOWN'}
    verifier=deterministic_verify(decision,[{'id':'a','kind':'inspect_kafka','payload':[]}],{'signals':[]},{'nodes':[]},None,None)
    result=combine_verdict({'verdict':'VERIFIED'},verifier)
    assert result['verdict']=='PARTIALLY_VERIFIED' and result['disagreement']


@pytest.mark.parametrize('diff,expected',[
 ('--- a/services/pricing.py\n+++ b/services/pricing.py\n-    return 1\n+    return 2','LOW'),
 ('--- a/services/app.py\n+++ b/services/app.py\n+    await query("SELECT 1")','HIGH'),
 ('--- a/infra/init.sql\n+++ b/infra/init.sql\n+ALTER TABLE t ADD x int','HIGH')])
def test_risk_never_authorizes_apply(diff,expected):
    result=patch_risk(diff);assert result['level']==expected and not result['automatic_apply_allowed']


def test_efficiency_reports_heuristic_duplicates_and_failures():
    rows=[{'id':str(i),'agent':'A','tool_name':'query_metrics','arguments':{},'status':s} for i,s in enumerate(['succeeded','succeeded','failed'])]
    r=tool_efficiency(rows)
    assert r['useful_tool_call']==r['redundant_tool_call']==r['failed_tool_call']==1


def test_new_agent_capabilities_do_not_import_evaluator():
    for name in ('hybrid.py','hybrid_tools.py','context_engineering.py','checkpoints.py','verification.py'):
        text=Path('/app/sentinel',name).read_text();tree=ast.parse(text)
        assert 'ground_truth_root_cause' not in text
        assert not any(isinstance(n,ast.ImportFrom) and any(x in (n.module or '') for x in ('scenarios','evaluator')) for n in ast.walk(tree))


def test_evidence_contract_exposes_bare_id_pattern_to_model():
    schema=RootCauseDecision.model_json_schema()
    for key in ('supporting_evidence','contradicting_evidence'):
        assert schema['properties'][key]['items']['pattern']==r'^E-[0-9a-f]{16}$'
    from pydantic import TypeAdapter
    from sentinel.hybrid_tools import EvidenceID
    adapter=TypeAdapter(EvidenceID)
    assert adapter.validate_python('E-0123456789abcdef')=='E-0123456789abcdef'
    with pytest.raises(ValueError): adapter.validate_python('E-0123456789abcdef: database evidence')


def test_checkpoint_resume_reuses_real_tool_without_duplicate(monkeypatch):
    import services.runtime as runtime
    from psycopg_pool import AsyncConnectionPool
    from psycopg.rows import dict_row
    from sentinel.storage import migrate
    from sentinel import checkpoints
    from sentinel.tool_registry import execute_tool
    from sentinel.hybrid import execute_pending
    async def run():
        pool=AsyncConnectionPool(runtime.DSN,open=False,kwargs={'autocommit':True,'row_factory':dict_row})
        monkeypatch.setattr(runtime,'pool',pool);await pool.open();await migrate()
        iid,rid=str(uuid.uuid4()),str(uuid.uuid4())
        await runtime.query("INSERT INTO incidents(id,status,signal) VALUES(%s,'test','{}')",(iid,))
        await runtime.query("INSERT INTO investigation_runs(id,incident_id,mode,status) VALUES(%s,%s,'TEST','completed')",(rid,iid))
        call={'id':'resume-probe','function':{'name':'inspect_redis','arguments':'{}'},'type':'function'}
        response={'role':'assistant','tool_calls':[call]}
        state={'messages':[response],'pending':response,'cursor':0,'calls_used':0}
        await checkpoints.save(iid,rid,'INVESTIGATING',state)
        result=await execute_tool('inspect_redis',{},iid,rid,'Investigator',call['id'])
        assert not result.get('error')
        # Simulates loss of process memory after successful DB commit, before cursor update.
        loaded=(await checkpoints.load(rid))['payload']
        await execute_pending(iid,rid,loaded,False)
        count=await runtime.query('SELECT count(*) n FROM tool_calls WHERE run_id=%s',(rid,),one=True)
        assert count['n']==1 and 'pending' not in loaded and loaded['calls_used']==1
        assert json.loads(loaded['messages'][-1]['content'])['resumed_from_ledger']
        denied=await execute_tool('inspect_redis',{},iid,rid,'Investigator','not-offered',allowed_names=['record_hypothesis'])
        assert denied.get('error') and not denied['evidence_ids']
        await pool.close()
    asyncio.run(run())
