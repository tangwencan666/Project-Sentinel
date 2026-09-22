"""Validate provenance links and experiment coverage without regrading any answer."""
import hashlib
import json
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from phase3_dataset import dataset_path
from post_eval_changes import api_default_only,worker_recovery_only

ROOT=Path(__file__).resolve().parents[1]


def load(path): return json.loads((ROOT/path).read_text(encoding='utf-8'))
def moment(value): return datetime.fromisoformat(value.replace('Z','+00:00'))


def main():
    baseline=load('evaluation/baselines/v1-pure-llm.json')
    expected=[r['scenario'] for r in baseline['results']]
    truth={r['scenario']:r['ground_truth'] for r in baseline['results']}
    suites=[json.loads(dataset_path(v).read_text(encoding='utf-8')) for v in ('v2','v3')]
    comparison=load('evaluation/comparison.json')
    checks=[];coverage=[];all_ids=[]
    def check(name,ok,detail=None): checks.append({'check':name,'passed':bool(ok),'detail':detail})
    check('same_framework_for_v2_and_v3',suites[0]['source_sha256']==suites[1]['source_sha256'])
    current={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in suites[0]['source_sha256']}
    same=current==suites[0]['source_sha256']
    post_change=ROOT/'evaluation/post-evaluation-default.json'
    if post_change.exists():
        change=json.loads(post_change.read_text(encoding='utf-8'))
        with zipfile.ZipFile(ROOT/change['frozen_framework']) as archive:
            check('benchmark_framework_archive_exact',all(hashlib.sha256(archive.read(p)).hexdigest()==h for p,h in suites[0]['source_sha256'].items()))
            old_api=archive.read('sentinel/api.py')
            old_app=archive.read('services/app.py')
        expected_changes={'sentinel/api.py'}
        worker_record=ROOT/'evaluation/fault-worker-recovery-fix.json'
        if worker_record.exists():
            expected_changes.add('services/app.py')
            check('only_declared_fault_worker_retry',worker_recovery_only(old_app,(ROOT/'services/app.py').read_bytes()),load('evaluation/fault-worker-recovery-fix.json'))
        check('only_declared_post_eval_changes',
            {p for p,h in current.items() if h!=suites[0]['source_sha256'][p]}==expected_changes
            and api_default_only(old_api,(ROOT/'sentinel/api.py').read_bytes()),change)
    else:check('host_sources_equal_formal_freeze',same)
    runtime=load('evaluation/runtime-manifest.json')
    check('runtime_sources_equal_formal_freeze',not runtime['mismatches'] and all(suites[0]['source_sha256'].get(p)==h for p,h in runtime['source_sha256'].items()),runtime['image'])
    proof=load('evaluation/pool-fixture-proof.json')
    declaration=load('evaluation/pool-validity-investigation.json')
    check('fixture_policy_declared_before_repair',moment(declaration['declared_at'])<moment(proof['at']))
    check('pool_fixture_independently_restored',proof['replacement_allowed'] and not any(s['saturation_proven'] for s in proof['before']) and any(s['saturation_proven'] for s in proof['after']))
    for suite in suites:
        mode=suite['version'];rows=suite['results']
        derived=next(v for v in comparison['versions'] if v['mode']==mode)
        check(mode+':eight_single_trials',suite['completed'] and [r['scenario'] for r in rows]==expected and len(rows)==8)
        check(mode+':same_model',suite['model']=='deepseek-chat')
        check(mode+':explicit_invalid_fixture_replacement',bool(suite.get('selection_policy')))
        check(mode+':displayed_scores_match_raw',derived['metrics']['root_accuracy']==sum(r.get('judgment',{}).get('root_cause_correct',False) for r in rows)/8 and derived['metrics']['service_accuracy']==sum(r.get('service_correct',False) for r in rows)/8)
        workflow=[c for r in rows for c in r.get('ledger',{}).get('usage',{}).get('calls',[]) if c['agent']!='Evaluator']
        expected_tokens=sum(c['total_tokens'] for c in workflow if c['status']=='succeeded') if all(c.get('total_tokens') is not None for c in workflow if c['status']=='succeeded') else None
        check(mode+':displayed_usage_matches_raw',derived['metrics']['total_tokens']==expected_tokens and derived['metrics']['llm_calls']==len(workflow))
        for row in rows:
            name=mode+':'+row['scenario'];rid=row.get('run_id');all_ids.append(rid)
            displayed=next(r for r in derived['results'] if r['scenario']==row['scenario'])
            check(name+':prediction_not_rewritten',displayed['predicted_root_cause']==(row.get('diagnosis') or {}).get('root_cause'))
            ledger=row.get('ledger',{});calls=ledger.get('usage',{}).get('calls',[]);evidence=ledger.get('evidence',[])
            tools=ledger.get('tool_calls',[]);known={e['id'] for e in evidence}
            check(name+':truth_unchanged',row.get('ground_truth')==truth[row['scenario']])
            check(name+':real_run_ledger',bool(rid and calls and tools and evidence) and ledger.get('run_id')==rid)
            check(name+':tool_links',all(t['run_id']==rid and t['finished_at'] and set(t['evidence_ids'] or []).issubset(known) for t in tools))
            check(name+':evidence_links',all(e['run_id']==rid and e['tool_call_id'] in {t['id'] for t in tools} for e in evidence))
            check(name+':provider_model',all(c['model']=='deepseek-chat' and c['run_id']==rid for c in calls))
            check(name+':usage_arithmetic',all(c['total_tokens']==c['input_tokens']+c['output_tokens'] for c in calls if all(c.get(k) is not None for k in ('total_tokens','input_tokens','output_tokens'))))
            run=next((r for r in ledger.get('runs',[]) if r['id']==rid),{})
            check(name+':judge_only_after_terminal',bool(run.get('finished_at')) and all(moment(c['started_at'])>=moment(run['finished_at']) for c in calls if c['agent']=='Evaluator'))
            check(name+':no_automatic_apply',row.get('patch_applied') is False)
            recovery=row.get('measured_recovery')
            if recovery:
                check(name+':server_recovery_measurements',recovery.get('not_an_ai_repair') is True and all(recovery.get(k,{}).get('source')=='Measured' for k in ('before','after')))
            if row.get('fault_replay_passed'):
                check(name+':patch_real_tests',row.get('tests_passed') is True and any(p.get('origin')=='AI_GENERATED' and p.get('artifact',{}).get('candidate_verified') for p in ledger.get('patches',[])))
        selected=[r for r in rows if r['scenario'] in suite['e2e_selection']['scenarios']]
        coverage.append({'version':mode,'selected_live_scenarios':suite['e2e_selection']['scenarios'],'executed':len(selected),
            'workflow_completed':sum(bool(r.get('workflow_completed')) for r in selected),
            'root_and_service_correct':sum(bool(r.get('judgment',{}).get('root_cause_correct') and r.get('service_correct')) for r in selected),
            'all_eight_workflow_completed':sum(bool(r.get('workflow_completed')) for r in rows)})
    check('distinct_formal_run_ids',None not in all_ids and len(set(all_ids))==16)
    result={'at':datetime.now(timezone.utc).isoformat(),'passed_integrity':all(c['passed'] for c in checks),
            'checks':checks,'live_e2e_coverage':coverage,'note':'Integrity pass is not an accuracy or workflow-success claim; failed diagnoses remain in the eight-trial denominator.'}
    (ROOT/'evaluation/artifact-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed_integrity':result['passed_integrity'],'checks':len(checks),'failed':[c for c in checks if not c['passed']],'coverage':coverage}))
    if not result['passed_integrity']: raise SystemExit(1)


if __name__=='__main__': main()
