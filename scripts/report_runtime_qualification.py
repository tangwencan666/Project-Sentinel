"""Keep every qualification revision visible, separate from the accuracy benchmark."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'evaluation/phase4'
versions=[]
for version in ('v3.1.1','v3.1.2','v3.1.3','v3.1.4'):
    artifacts=[]
    for path in folder.glob(version+'-qualification*.json'):
        doc=json.loads(path.read_text(encoding='utf-8'))
        if 'results' not in doc: continue
        artifacts.append((path,doc))
    if not artifacts: continue
    # Continuations preserve all earlier rows; select the longest known prefix,
    # preferring a completed suite, never selecting by diagnosis or pass count.
    path,suite=max(artifacts,key=lambda x:(len(x[1]['results']),bool(x[1].get('completed')),x[0].stat().st_mtime_ns))
    rows=[]
    for row in suite['results']:
        calls=row.get('ledger',{}).get('usage',{}).get('calls',[])
        rows.append({'scenario':row['scenario'],'run_id':row.get('run_id'),'incident_id':row['incident_id'],
            'workflow_completed':row.get('workflow_completed'),'patch_verified':row.get('patch_verified'),
            'error':row.get('error'),'llm_calls':len(calls),
            'total_tokens':sum(c['total_tokens'] for c in calls if c['status']=='succeeded') if all(c.get('total_tokens') is not None for c in calls if c['status']=='succeeded') else None,
            'confirmed_output_truncations':sum((c.get('diagnostics') or {}).get('finish_reason')=='length' for c in calls)})
    fail=any(r['workflow_completed'] is False for r in rows)
    versions.append({'version':version,'scope':'RUNTIME_QUALIFICATION_NOT_ACCURACY','graded':False,
        'selected_artifact':str(path.relative_to(ROOT)).replace('\\','/'),
        'status':'QUALIFIED' if suite.get('passed') else 'NOT_QUALIFIED' if fail or suite.get('completed') else 'INTERRUPTED' if suite.get('runner_error') else 'IN_PROGRESS',
        'completed_suite':suite.get('completed',False),'completed_workflows':sum(r['workflow_completed'] is True for r in rows),
        'dispatched':len(rows),'preregistered':5,'results':rows,
        'retained_artifacts':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p,_ in artifacts]})
result={'versions':versions,'accuracy_denominator_contribution':0,
        'note':'Never substitutes a later qualification for a first-controlled result. Failures, interruptions and source archives retained.'}
(folder/'runtime-qualification-report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([{'version':v['version'],'status':v['status'],'workflow_completed':v['completed_workflows'],'dispatched':v['dispatched']} for v in versions]))
