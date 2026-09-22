"""Offline integrity/capability audit; dynamic adversarial results are separate."""
import ast
import hashlib
import json
import argparse
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='static-audit-final.json');args=parser.parse_args()
    assert Path(args.output).name==args.output
    output=ROOT/'evaluation/phase4'/args.output
    if output.exists(): raise FileExistsError('Keep previous audit evidence; choose another filename')
    baseline=ROOT/'evaluation/baselines';checks={}
    for line in (baseline/'manifest.sha256').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1)
        checks['baseline/'+name]=hashlib.sha256((baseline/name).read_bytes()).hexdigest()==digest
    benchmark=json.loads((ROOT/'evaluation/benchmarks/sentinel-benchmark-v1/manifest.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(ROOT/'evaluation/benchmarks/sentinel-benchmark-v1/business-source.zip') as archive:
        for name,digest in benchmark['protected_sha256'].items():
            checks['benchmark-v1-archive/'+name]=hashlib.sha256(archive.read(name)).hexdigest()==digest
    current=json.loads((ROOT/'evaluation/benchmarks/sentinel-benchmark-v2/manifest.json').read_text(encoding='utf-8'))
    for name,digest in current['protected_sha256'].items():
        checks['benchmark-v2-current/'+name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    for name in current['unchanged_from_v1']:
        checks['unchanged-semantics/'+name]=current['protected_sha256'][name]==benchmark['protected_sha256'][name]
    for name,digest in {'v3.1-first-controlled.json':'f8c2818edec2c1c521571a09c0193c4e1f50dfc96a5ea724057df09749c768cf',
        'v4-first-controlled.json':'454f2181cdb6a26111bc1b3c49e2259da5c76a1910dc1dc342a935d330658faa'}.items():
        checks['frozen-formal/'+name]=hashlib.sha256((ROOT/'evaluation/results'/name).read_bytes()).hexdigest()==digest
    modules=['runtime_agent','runtime_tools','runtime_state','structured_output','hybrid','hybrid_tools',
             'provider','storage','contracts','evidence','tool_registry','context_engineering','verification',
             'convergence','context_delivery','redaction_walk','submission_contract','budget_accounting','field_repair','evidence_compiler','infra_observations',
             'generic_patching','multiservice_sandbox','sandbox_worker','remediation','diagnostics']
    findings=[]
    for module in modules:
        path=ROOT/'sentinel'/(module+'.py');text=path.read_text(encoding='utf-8');tree=ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and any(word in (node.module or '') for word in ('scenarios','evaluator')):
                findings.append({'file':str(path.relative_to(ROOT)),'line':node.lineno,'kind':'truth import'})
        if 'ground_truth_root_cause' in text: findings.append({'file':module,'kind':'truth field'})
        if module.startswith('runtime_') and 'scenario_id' in text: findings.append({'file':module,'kind':'scenario branch'})
    key=None
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('LLM_API_KEY='): key=line.split('=',1)[1].strip().strip('"').strip("'").encode()
    leaks=[]
    unsafe_archive_entries=[]
    if key:
        for folder in ('sentinel','services','tests','scripts','docs','evaluation','web'):
            for path in (ROOT/folder).rglob('*'):
                if path.is_file() and path.suffix in ('.py','.md','.json','.html','.js','.css','.log') and key in path.read_bytes():
                    leaks.append(str(path.relative_to(ROOT)))
        for folder in ('evaluation','outputs'):
            for path in (ROOT/folder).rglob('*.zip'):
                with zipfile.ZipFile(path) as archive:
                    for entry in archive.namelist():
                        if Path(entry).name=='.env': unsafe_archive_entries.append(str(path.relative_to(ROOT))+'!'+entry)
                        if key in archive.read(entry): leaks.append(str(path.relative_to(ROOT))+'!'+entry)
    result={'passed':all(checks.values()) and not findings and not leaks and not unsafe_archive_entries,'integrity':checks,
            'capability_findings':findings,'secret_match_files':leaks,
            'unsafe_archive_entries':unsafe_archive_entries,
            'scope':'Static capability and exact-secret/integrity checks only; not a replacement for adversarial or OS sandbox testing.'}
    output.write_text(json.dumps(result,indent=2),encoding='utf-8');output.chmod(0o444)
    print(json.dumps({'passed':result['passed'],'checks':len(checks),'findings':len(findings),'secret_matches':len(leaks)}))
    if not result['passed']: raise SystemExit(1)
if __name__=='__main__': main()
