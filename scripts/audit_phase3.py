"""Static capability audit and frozen artifact verification; no model calls."""
import ast
import hashlib
import json
from pathlib import Path
import re
import zipfile
from post_eval_changes import worker_recovery_only

ROOT=Path(__file__).resolve().parents[1]
KEYWORDS=('mock','fake','hardcoded','scenario_id','ground_truth','TODO','FIXME')
AGENT_MODULES=('agent','hybrid','hybrid_tools','context_engineering','verification','checkpoints',
               'tool_registry','evidence','provider','contracts','storage','security','patching','ai_patching','recovery','sandbox_server')


def main():
    findings=[];keyword_hits=[]
    for p in [p for d in ('sentinel','services','tests','scripts','web') for p in (ROOT/d).rglob('*') if p.suffix in ('.py','.js','.html','.css')]:
        text=p.read_text(encoding='utf-8-sig')
        for number,line in enumerate(text.splitlines(),1):
            hits=[key for key in KEYWORDS if key.lower() in line.lower()]
            if hits: keyword_hits.append({'path':p.relative_to(ROOT).as_posix(),'line':number,'keywords':hits})
    for module in AGENT_MODULES:
        p=ROOT/'sentinel'/(module+'.py');text=p.read_text(encoding='utf-8-sig');tree=ast.parse(text)
        for n in ast.walk(tree):
            if isinstance(n,ast.ImportFrom) and any(x in (n.module or '') for x in ('evaluator','scenarios')):
                findings.append({'path':str(p),'line':n.lineno,'issue':'agent import reaches control/evaluation module'})
        if 'ground_truth_root_cause' in text: findings.append({'path':str(p),'issue':'truth field in investigator graph'})
        if module in ('hybrid','hybrid_tools','verification','context_engineering'):
            if 'scenario_id' in text: findings.append({'path':str(p),'issue':'scenario-dependent agent branch'})
    manifest=json.loads((ROOT/'evaluation/baselines/manifest.json').read_text())
    baseline_integrity={name:hashlib.sha256((ROOT/'evaluation/baselines'/name).read_bytes()).hexdigest()==expected
                        for name,expected in manifest['file_hashes'].items()}
    with zipfile.ZipFile(ROOT/'evaluation/baselines/archive.zip') as archive:
        archived_integrity=all(hashlib.sha256(archive.read(name)).hexdigest()==expected for name,expected in manifest['archived_source_hashes'].items())
        original_app=archive.read('services/app.py')
    immutable_definitions={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==manifest['archived_source_hashes'][name]
                           for name in ('sentinel/scenarios.py','sentinel/evaluator.py','services/app.py','services/pricing.py','tests/pricing_contract.py')}
    declared_worker_retry=(ROOT/'evaluation/fault-worker-recovery-fix.json').exists() and worker_recovery_only(original_app,(ROOT/'services/app.py').read_bytes())
    accepted_definitions=all(unchanged or (name=='services/app.py' and declared_worker_retry) for name,unchanged in immutable_definitions.items())
    # Exact configured key check. Never print or persist the key or its location snippet.
    env={}
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            key,value=line.split('=',1);env[key.strip()]=value.strip().strip('"').strip("'")
    secret=env.get('LLM_API_KEY','').encode();secret_matches=[]
    for folder in ('sentinel','services','tests','scripts','web','evaluation','docs'):
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in ('.py','.js','.html','.css','.json','.md','.log') and secret and secret in p.read_bytes():
                secret_matches.append(p.relative_to(ROOT).as_posix())
    result={'baseline_files_unchanged':baseline_integrity,'archive_members_unchanged':archived_integrity,
        'fault_business_and_grader_byte_unchanged':immutable_definitions,
        'declared_post_evaluation_worker_retry_only':declared_worker_retry,
        'capability_findings':findings,'secret_match_files':secret_matches,
        'keyword_hits':keyword_hits,'keyword_classification':{
            'scenario_id / ground_truth':'Allowed in control plane, experiment runners, operator dashboard, frozen artifacts and post-run evaluator; excluded from Investigator capabilities.',
            'mock / fake':'Protocol error harness and audit vocabulary must not be counted as diagnosis accuracy evidence.',
            'hardcoded':'Configured service dependencies and baseline rules are explicit architecture/predicates; no scenario-key answer branch in hybrid.',
            'TODO / FIXME':'Inspect every returned source location; no hidden completion claims.'},
        'honesty_checks':{'token_usage':'Provider input/output fields; compression is explicitly Estimated.',
            'tool_calls':'Persisted audit rows, including failed and duplicate requests.',
            'before_after':'Server measurements; operator restoration explicitly not an AI repair.',
            'critic':'Independent model session plus deterministic veto; no correctness guarantee.',
            'replay':'Separate recorded-runs endpoint and RECORDED RUN UI label.'},
        'limits':['Static capability checks are not an OS sandbox proof.','Evaluator and Investigator share the service process and database server.',
                  'Configured infrastructure topology edges are declared architecture, not measured traces.',
                  'Tool efficiency is a retrospective duplicate-query proxy, not human relevance adjudication.']}
    result['passed']=all(baseline_integrity.values()) and archived_integrity and accepted_definitions and not findings and not secret_matches
    output=ROOT/'evaluation/audit.json';output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':result['passed'],'keyword_locations':len(keyword_hits),'capability_findings':len(findings),'secret_matches':len(secret_matches)},ensure_ascii=True))
    if not result['passed']: raise SystemExit(1)


if __name__=='__main__': main()
