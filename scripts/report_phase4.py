"""Offline six-way report, same grading decisions and duplicate-query proxy as phase 3."""
from collections import Counter,defaultdict
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from sentinel.context_engineering import tool_efficiency
from report_phase3 import totals

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def write(path,value):
    path.parent.mkdir(exist_ok=True,parents=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def category(error):
    text=json.dumps(error,ensure_ascii=False).upper()
    if isinstance(error,dict) and error.get('error_code')=='TimeoutError': return 'BUDGET_FAILURE'
    for words,name in [(['BUDGET','CONTEXT_OVERFLOW'],'BUDGET_FAILURE'),
        (['INVALID_ARGUMENT_JSON','INVALID_PROVIDER_JSON','SCHEMA','FIELD_TOO_LONG','VALIDATIONERROR'],'SCHEMA_FAILURE'),
        (['UNREAD','CITATION'],'CITATION_FAILURE'),
        (['STATE_TRANSITION','HYPOTHESIS_NOT_CREATED'],'STATE_FAILURE'),
        (['TOOL_NOT_AVAILABLE','TOOL NOT OFFERED','ENVELOPE','CIRCUIT_BREAKER'],'PROTOCOL_FAILURE'),
        (['PROVIDER','LLM_TIMEOUT'],'PROVIDER_FAILURE'),(['TOOL'],'TOOL_FAILURE')]:
        if any(w in text for w in words): return name
    return 'STATE_FAILURE' if error else None

def diagnostics(row):
    ledger=row.get('ledger',{});tools=ledger.get('tool_calls',[])
    calls=ledger.get('usage',{}).get('calls',[])
    errors=[t['error'] for t in tools if t.get('error')]
    codes=Counter(e.get('error_code',e.get('code','UNKNOWN')) for e in errors)
    repeated=0;previous=None
    for t in tools:
        sig=json.dumps([t['tool_name'],t.get('arguments'),t.get('error')],sort_keys=True)
        if t.get('status')=='failed' and sig==previous: repeated+=1
        previous=sig if t.get('status')=='failed' else None
    extra=[c.get('diagnostics') or {} for c in calls if c.get('agent')!='Investigator']
    terminal_budget=category(row.get('error'))=='BUDGET_FAILURE' and not any(e==row.get('error') for e in errors)
    return {'invalid_json_count':codes['INVALID_ARGUMENT_JSON']+sum(bool(c.get('parse_error')) for c in extra),
        'schema_failure_count':codes['SCHEMA_VALIDATION_FAILED']+codes['FIELD_TOO_LONG']+sum(bool(c.get('schema_error')) for c in extra),
        'protocol_failure_count':sum(category(e)=='PROTOCOL_FAILURE' for e in errors),
        'budget_failure_count':sum(category(e)=='BUDGET_FAILURE' for e in errors)+int(terminal_budget),
        'repeated_failed_calls':repeated,'tool_not_offered_count':codes['TOOL_NOT_AVAILABLE_IN_PHASE'],
        'unread_citation_count':codes['UNREAD_CITATION'],'error_code_counts':dict(codes),
        'secondary_causes':sorted({category(e) for e in errors if category(e)})}

def add_legacy_diagnostics(version):
    """Retrospective ledger counts; missing provider parse instrumentation stays unknown."""
    metrics=version['metrics'];counts=Counter()
    for row in version['results']:
        raw=ROOT/'evaluation/runs'/(row['run_id']+'.json')
        record=read(raw) if raw.exists() else {}
        errors=[t.get('error') for t in record.get('tool_calls',[]) if t.get('error')]
        texts=[json.dumps(e,ensure_ascii=False).lower() for e in errors]
        not_offered=sum('tool not offered' in text for text in texts)
        unread=sum('code citation not read' in text for text in texts)
        row['failure_classification']='SUCCESS' if row['workflow_completed'] and row['correct'] else 'REASONING_FAILURE' if row['workflow_completed'] else category(row.get('error')) or 'STATE_FAILURE'
        row['tool_not_offered_count']=not_offered;row['unread_citation_count']=unread
        row['legacy_parse_instrumentation_available']=False
        counts['tool_not_offered_count']+=not_offered;counts['unread_citation_count']+=unread
    metrics.update(counts)
    # HTTP-success logs from old versions cannot prove JSON/schema success.
    for key in ('invalid_json_count','schema_failure_count','protocol_failure_count','budget_failure_count','repeated_failed_calls'):
        metrics[key]=None
    metrics['failure_classes']=dict(Counter(r['failure_classification'] for r in version['results']))
    metrics['diagnostic_coverage']='Legacy: not-offered/unread-citation counts reconstructed from persisted tool errors; other detailed counters unavailable, not zero.'

def make_version(key,path):
    suite=read(path);rows=[];workflow_calls=[]
    confounded={iid for intervention in suite.get('operator_interventions',[]) for iid in intervention.get('affected_trials',[])}
    for original in suite['results']:
        ledger=original.get('ledger',{});calls=ledger.get('usage',{}).get('calls',[])
        workflow=[c for c in calls if c['agent']!='Evaluator'];workflow_calls+=workflow
        diag=original.get('diagnosis') or {};complete=original.get('workflow_completed',False)
        correct=original.get('judgment',{}).get('root_cause_correct',False)
        item={'scenario':original['scenario'],'incident_id':original['incident_id'],'run_id':original.get('run_id',ledger.get('run_id')),
            'ground_truth':original.get('ground_truth'),'expected_service':original.get('expected_service'),
            'predicted_root_cause':diag.get('root_cause'),'predicted_service':diag.get('affected_service'),
            'correct':correct,'service_correct':original.get('service_correct',False),'workflow_completed':complete,
            'duration':original.get('duration_seconds'),'tool_calls':len(ledger.get('tool_calls',[])),
            'efficiency':tool_efficiency(ledger.get('tool_calls',[])),**totals(workflow),**diagnostics(original),
            'failure_classification':'SUCCESS' if complete and correct else 'REASONING_FAILURE' if complete else category(original.get('error') or original.get('runner_error')) or 'STATE_FAILURE',
            'error':original.get('error'),'grading_status':original.get('grading_status','graded'),
            'fixture_confounded':original['incident_id'] in confounded,
            'fixture_note':'Unrelated notification consumer startup failure coexisted with target fault; first dispatch retained, never rerun.' if original['incident_id'] in confounded else None,
            'judgment':original.get('judgment'),'critic_result':original.get('critic'),
            'patch_result':{k:original.get(k) for k in ('patch_requested','patch_generated','tests_passed','fault_replay_passed')},
            'evaluator_usage':totals([c for c in calls if c['agent']=='Evaluator']),
            'failure_analysis':(original.get('judgment') or {}).get('explanation','')+(' | '+json.dumps(original['error'],ensure_ascii=False) if original.get('error') else '')}
        rows.append(item)
        if item['run_id']:
            by_role=defaultdict(list)
            for call in calls: by_role[call['agent']].append(call)
            recorded={k:ledger.get(k,[]) for k in ('tool_calls','evidence','hypotheses','patches')}
            recorded.update(display_mode='RECORDED RUN',live=False,steps=original.get('recorded_incident',{}).get('steps',[]),
                critic=item['critic_result'],workflow_completed=complete,measured=original.get('measured'),
                measured_recovery=original.get('measured_recovery'),
                tokens_by_phase=[{'agent':name,**totals(cs)} for name,cs in by_role.items()],
                provider_calls=calls,fixture_confounded=item['fixture_confounded'],fixture_note=item['fixture_note'],
                context_measurements=original.get('context',{}).get('measurements',[]))
            write(ROOT/'evaluation/runs'/(item['run_id']+'.json'),recorded)
    n=len(rows);completed=sum(r['workflow_completed'] for r in rows)
    correct=sum(r['correct'] for r in rows);count_tools=sum(r['tool_calls'] for r in rows)
    useful=sum(r['efficiency'].get('useful_tool_call',0) for r in rows)
    durations=[r['duration'] for r in rows if r['duration'] is not None]
    metrics={**totals(workflow_calls),'scenarios':n,'workflow_completed':completed,
        'workflow_completion_rate':completed/n if n else None,'root_accuracy':correct/n if n else None,
        'conditional_root_accuracy':sum(r['correct'] and r['workflow_completed'] for r in rows)/completed if completed else None,
        'service_accuracy':sum(r['service_correct'] for r in rows)/n if n else None,
        'tool_calls':count_tools,'useful_rate':useful/count_tools if count_tools else None,'useful_tool_calls':useful,
        'average_duration':sum(durations)/len(durations) if durations else None,
        'critic_false_accept':sum(not r['correct'] and (r['critic_result'] or {}).get('verdict')=='VERIFIED' for r in rows),
        'failure_classes':dict(Counter(r['failure_classification'] for r in rows))}
    metrics['critic_reviewed_runs']=sum(bool(r['critic_result']) for r in rows)
    metrics['redundant_tool_calls']=sum(r['efficiency'].get('redundant_tool_call',0) for r in rows)
    metrics['failed_tool_calls']=sum(r['efficiency'].get('failed_tool_call',0) for r in rows)
    metrics['ungraded_runs']=sum(r['grading_status']=='ungraded' for r in rows)
    metrics['conditional_accuracy_denominator']=completed
    metrics['confounded_trials']=sum(r['fixture_confounded'] for r in rows)
    unconfounded=[r for r in rows if not r['fixture_confounded']]
    metrics['unconfounded_subset_denominator']=len(unconfounded)
    metrics['unconfounded_subset_accuracy']=sum(r['correct'] for r in unconfounded)/len(unconfounded) if unconfounded else None
    metrics['critic_verified_count']=sum((r['critic_result'] or {}).get('verdict')=='VERIFIED' for r in rows)
    metrics['critic_false_accept_rate_given_verified']=metrics['critic_false_accept']/metrics['critic_verified_count'] if metrics['critic_verified_count'] else None
    for metric in ('invalid_json_count','schema_failure_count','protocol_failure_count','budget_failure_count',
                   'repeated_failed_calls','tool_not_offered_count','unread_citation_count'):
        metrics[metric]=sum(r[metric] for r in rows)
    patches=[r for r in rows if r['patch_result']['patch_requested'] or r['patch_result']['patch_generated']]
    metrics.update(patch_denominator=len(patches),patch_success=sum(bool(r['patch_result']['fault_replay_passed']) for r in patches)/len(patches) if patches else None)
    return {'key':key,'label':{'v3.1':'Reliable Runtime V3.1','v4':'Evidence Compiler V4','v4.1':'Final Runtime V4.1'}[key],
        'mode':suite['version'],'source_file':str(path.relative_to(ROOT)).replace('\\','/'),
        'completed':suite['completed'],'metrics':metrics,'results':rows,'budget_policy':suite['budget_policy'],
        'comparison_eligible':not confounded,'operator_interventions':suite.get('operator_interventions',[]),
        'comparison_note':'First dispatch aggregate contains fixture confounds; excluded from Pareto ranking. Clean subset is not an eight-scenario estimate.' if confounded else None}

def pareto(versions):
    def coordinates(v):
        m=v['metrics'];return (m['root_accuracy'],-m['total_tokens'],-m['average_duration'],m['workflow_completed']/m['scenarios'])
    eligible=[v for v in versions if v.get('completed') and v.get('comparison_eligible',True) and all(v['metrics'].get(k) is not None for k in ('root_accuracy','total_tokens','average_duration'))]
    out=[]
    for version in eligible:
        value=coordinates(version);dominators=[]
        for other in eligible:
            if other['key']==version['key']: continue
            score=coordinates(other)
            if all(a>=b for a,b in zip(score,value)) and any(a>b for a,b in zip(score,value)): dominators.append(other['key'])
        out.append({'version':version['key'],'on_frontier':not dominators,'dominated_by':dominators})
    return out

def main():
    original=ROOT/'evaluation/phase4/phase3-comparison-frozen.json'
    if not original.exists():
        with original.open('xb') as stream: stream.write((ROOT/'evaluation/comparison.json').read_bytes())
        original.chmod(0o444)
    base=read(original);versions=base['versions']
    for version in versions:
        m=version['metrics'];m['workflow_completion_rate']=m['workflow_completed']/m['scenarios']
        m['conditional_root_accuracy']=sum(r['correct'] and r['workflow_completed'] for r in version['results'])/m['workflow_completed'] if m['workflow_completed'] else None
        add_legacy_diagnostics(version)
    for key in ('v3.1','v4'):
        path=ROOT/'evaluation/results'/f'{key}-first-controlled.json'
        if path.exists(): versions.append(make_version(key,path))
    result={**base,'generated_at':datetime.now(timezone.utc).isoformat(),'versions':versions,
        'all_completed':len(versions)==6 and all(v['completed'] for v in versions),
        'pareto':pareto(versions),'pareto_excluded':[{'version':v['key'],'reason':v.get('comparison_note')} for v in versions if not v.get('comparison_eligible',True)],'benchmark_id':'sentinel-benchmark-v1',
        'ai_only_pareto':pareto([v for v in versions if v['key']!='rule']),
        'complete_workflow_ai_pareto':pareto([v for v in versions if v['key']!='rule' and v['metrics']['workflow_completed']==v['metrics']['scenarios']]),
        'interpretation_limits':['One controlled trial per scenario/version, n=8; no statistical generalization claim.',
            'Rule baseline encodes domain predicates for this benchmark; zero LLM tokens do not imply general incident intelligence.',
            'Pareto membership is a descriptive tradeoff, not a recommendation: early failures may consume fewer tokens. A separate AI frontier requires all eight workflows completed.',
            'V3 token reduction coincided with six workflow failures and is not a successful optimization.',
            'V3.1 changes control state, error correction and reserved budgets; not a one-variable compression ablation.',
            'V4 includes separately qualified follow-up runtime corrections plus the compiler. V3.1-to-V4 is not a pure compression ablation; qualification trials are excluded.',
            'V4 first pool/N+1 dispatches were confounded by an unrelated failed notification consumer after Docker restart. Original scores are retained; the version is excluded from Pareto ranking.',
            'Costs unknown unless operator-configured pricing exists; workflow token totals exclude the judge.'],
        'dataset_note':'历史 V3 仅完成 2/8，不能将其 Token 降低宣传为成功优化。V3.1/V4 保留首轮正式结果；额外纠错预算明确列出。'}
    write(ROOT/'evaluation/phase4/comparison.json',result)
    release=ROOT/'evaluation/results/v4.1-first-controlled.json'
    if release.exists():
        suite=read(release)
        if suite.get('completed'):
            write(ROOT/'evaluation/phase4/final-release-report.json',{'status':'completed','benchmark_id':suite['benchmark_id'],
                'ground_truth_version':suite['ground_truth_version'],'comparison_limitations':suite['comparison_limitations'],
                'version':make_version('v4.1',release),'included_in_historic_pareto':False})
    print(json.dumps({v['key']:v['metrics'] for v in versions},ensure_ascii=True,indent=2))
if __name__=='__main__': main()
