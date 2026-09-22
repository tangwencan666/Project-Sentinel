"""Derive UI/report artifacts from retained measured records; never regrade diagnoses."""
import json
from pathlib import Path
import sys
import zipfile
from collections import defaultdict
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from sentinel.context_engineering import tool_efficiency
from phase3_dataset import dataset_path


def totals(calls):
    good=[c for c in calls if c['status']=='succeeded']
    def amount(key): return sum(c[key] for c in good) if all(c.get(key) is not None for c in good) else None
    return {'llm_calls':len(calls),'input_tokens':amount('input_tokens'),'output_tokens':amount('output_tokens'),
            'total_tokens':amount('total_tokens'),'missing_usage_calls':sum(c.get('total_tokens') is None for c in calls),
            'cost':None}


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def development_usage():
    """Retain the cost of failed preflights; multiple snapshots may contain the same call."""
    paths=sorted((ROOT/'evaluation').glob('resume-*.json'))
    paths += [ROOT/'evaluation/aborted-second-run.json',ROOT/'evaluation/results/v2-hybrid-interrupted-schema-loop.json']
    unique={};artifacts=[]
    for path in paths:
        if not path.exists(): continue
        data=json.loads(path.read_text(encoding='utf-8'))
        ledgers=[r.get('ledger',{}) for r in data.get('results',[])] if 'results' in data else [data.get('ledger',{})]
        calls=[c for ledger in ledgers for c in ledger.get('usage',{}).get('calls',[])]
        for call in calls:
            previous=unique.get(call['id'],{})
            if (call.get('finished_at') or '') >= (previous.get('finished_at') or ''): unique[call['id']]=call
        artifacts.append({'file':path.relative_to(ROOT).as_posix(),'calls_in_snapshot':len(calls),
                          'known_tokens':sum(c.get('total_tokens') or 0 for c in calls)})
    # Excluded fixture attempts remain visible as expense, never counted twice in valid accuracy.
    for version,name in [('v2','v2-hybrid.json'),('v3','v3-context-optimized.json')]:
        selected=dataset_path(version)
        if selected.name==name: continue
        source=json.loads((ROOT/'evaluation/results'/name).read_text(encoding='utf-8'))
        row=next(r for r in source['results'] if r['scenario']=='pool_exhaustion')
        calls=row['ledger']['usage']['calls']
        for call in calls: unique[call['id']]=call
        artifacts.append({'file':'evaluation/results/'+name+' [invalid pool fixture only]','calls_in_snapshot':len(calls),
                          'known_tokens':sum(c.get('total_tokens') or 0 for c in calls)})
    calls=list(unique.values())
    return {'scope':'Development, restart preflights and explicitly interrupted framework suite; excluded from formal accuracy, never erased. Deduplicated by call ID.',
        'artifacts':artifacts,**totals(calls),
        'known_tokens':sum(c.get('total_tokens') or 0 for c in calls),
        'note':'Missing usage is unknown, not zero. Provider connectivity probes are not included in run ledgers. Cost is Unknown.'}


def main():
    with zipfile.ZipFile(ROOT/'evaluation/baselines/archive.zip') as archive:
        ledger=json.loads(archive.read('docs/phase2-run-ledger.json'))
        calls=json.loads(archive.read('docs/phase2-llm-call-ledger.json'))
    versions=[];run_dir=ROOT/'evaluation/runs'
    for key,label,file,mode in [
        ('rule','Rule Baseline','baselines/v1-rule-based.json','RULE_BASED'),
        ('v1','Pure LLM V1','baselines/v1-pure-llm.json','AI'),
        ('v2','Hybrid V2','results/v2-hybrid.json','HYBRID_V2'),
        ('v3','Context Optimized V3','results/v3-context-optimized.json','HYBRID_V3')]:
        path=dataset_path(key) if key in ('v2','v3') else ROOT/'evaluation'/file;rows=[];all_calls=[];all_tools=[]
        source=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'results':[]}
        for row in source['results']:
            rid=row.get('run_id')
            if key in ('rule','v1'):
                detail=next(r for r in ledger if r['run_id']==rid)
                run_calls=[c for c in calls if c['run_id']==rid]
                item=dict(row)
                item['workflow_completed']=row.get('run_status')=='completed'
            else:
                detail=row.get('ledger') or {};run_calls=detail.get('usage',{}).get('calls',[])
                diagnosis=row.get('diagnosis') or {}
                item={'scenario':row['scenario'],'incident_id':row['incident_id'],'run_id':rid,
                    'ground_truth':row.get('ground_truth'),'predicted_root_cause':diagnosis.get('root_cause'),
                    'predicted_service':diagnosis.get('affected_service'),
                    'correct':row.get('judgment',{}).get('root_cause_correct',False),'service_correct':row.get('service_correct',False),
                    'duration':row.get('duration_seconds'),'tool_calls':row.get('tool_calls'),
                    'patch_result':{k:row.get(k) for k in ('patch_requested','patch_generated','tests_passed','fault_replay_passed')},
                    'critic_result':row.get('critic'),'judgment':row.get('judgment'),
                    'workflow_completed':row.get('workflow_completed',False),'error':row.get('error') or row.get('runner_error')}
                detail={**detail,'steps':row.get('recorded_incident',{}).get('steps',[])}
            workflow=[c for c in run_calls if c['agent']!='Evaluator'];all_calls+=workflow
            tools=detail.get('tool_calls',[]);all_tools+=tools
            item.update(totals(workflow),efficiency=tool_efficiency(tools),
                        evaluator_usage=totals([c for c in run_calls if c['agent']=='Evaluator']))
            phases=defaultdict(list)
            for c in run_calls: phases[c['agent']].append(c)
            recorded={k:detail.get(k,[]) for k in ('tool_calls','evidence','hypotheses','steps','patches')}
            recorded.update(display_mode='RECORDED RUN',live=False,
                critic=item.get('critic_result'),
                workflow_completed=item.get('workflow_completed'),
                measured=row.get('measured'),measured_recovery=row.get('measured_recovery'),
                tokens_by_phase=[{'agent':name,'calls':len(cs),**totals(cs)} for name,cs in phases.items()],
                context_measurements=row.get('context',{}).get('measurements',[]))
            if rid: write(run_dir/(rid+'.json'),recorded)
            judgment=item.get('judgment') or item.get('original_judgment') or {}
            explanation=judgment.get('explanation') or ''
            failure=item.get('error')
            item['failure_analysis']=explanation+(' | Workflow error: '+json.dumps(failure,ensure_ascii=False) if failure else '')
            rows.append(item)
        patches=[r for r in rows if r['patch_result'].get('patch_requested') or r['patch_result'].get('patch_generated')]
        # Duplicate classification resets for each run, including the V1 retrospective analysis.
        counts={k:sum(r['efficiency'].get(k,0) for r in rows) for k in ('useful_tool_call','redundant_tool_call','failed_tool_call','total')}
        valid_durations=[r['duration'] for r in rows if r.get('duration') is not None]
        metrics={**totals(all_calls),'root_accuracy':sum(r['correct'] for r in rows)/len(rows) if rows else None,
            'service_accuracy':sum(r['service_correct'] for r in rows)/len(rows) if rows else None,
            'tool_calls':len(all_tools),'useful_rate':counts['useful_tool_call']/counts['total'] if counts['total'] else None,
            'useful_tool_calls':counts['useful_tool_call'] if rows else None,
            'redundant_tool_calls':counts['redundant_tool_call'] if rows else None,
            'failed_tool_calls':counts['failed_tool_call'] if rows else None,
            'average_duration':sum(valid_durations)/len(valid_durations) if valid_durations else None,
            'missing_duration_runs':len(rows)-len(valid_durations),
            'critic_false_accept':sum(not r['correct'] and (r.get('critic_result') or {}).get('verdict')=='VERIFIED' for r in rows),
            'critic_verified_count':sum((r.get('critic_result') or {}).get('verdict')=='VERIFIED' for r in rows),
            'correct_and_verified':sum(r['correct'] and (r.get('critic_result') or {}).get('verdict')=='VERIFIED' for r in rows),
            'patch_success':sum(r['patch_result'].get('fault_replay_passed',False) for r in patches)/len(patches) if patches else None,
            'patch_denominator':len(patches),'efficiency_counts':counts,'scenarios':len(rows),
            'workflow_completed':sum(bool(r.get('workflow_completed')) for r in rows)}
        if not rows:
            for field in ('llm_calls','input_tokens','output_tokens','total_tokens','tool_calls','critic_false_accept'): metrics[field]=None
        versions.append({'key':key,'label':label,'mode':mode,'metrics':metrics,'results':rows,
                         'source_file':path.relative_to(ROOT).as_posix(),'selection_policy':source.get('selection_policy'),
                         'completed':source.get('completed',key in ('rule','v1'))})
    result={'generated_at':datetime.now(timezone.utc).isoformat(),'versions':versions,
            'scenarios':[r['scenario'] for r in versions[0]['results']],
            'usage_scope':'Workflow only, excluding Evaluator. Evaluator separately retained per row.',
            'single_valid_trial_per_scenario':True,'cost':'Unknown','all_completed':all(v['completed'] for v in versions),
            'development_usage':development_usage()}
    result['dataset_note']='连接池初次注入未生效，经同镜像重启前后测量证明并各补测一次；主表采用首次有效试验，原始两组结果及其他所有错误均保留。' if any(v.get('selection_policy') for v in versions) else '连接池初次注入有效性正在核查；当前展示原始尝试记录，不能将该条当作已验证的连接池故障实验。'
    write(ROOT/'evaluation/comparison.json',result)
    print(json.dumps({v['key']:v['metrics'] for v in versions},ensure_ascii=True,indent=2))


if __name__=='__main__': main()
