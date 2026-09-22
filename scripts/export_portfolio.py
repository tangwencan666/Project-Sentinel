"""Build public read-only projections from frozen records. Never modifies originals or calls a model."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'portfolio/data'
RID = '759044e6-c016-489b-a459-137ca4846462'
SOURCE = ROOT / 'evaluation/results/v4.1-first-controlled.json'
SEALED = '74b48f0cc7a3f341ca0a088a50054fa0c45209034d12aa4f5de46a4f1fa2c81a'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if re.search(r'^(authorization|api_key|password|secret|access_token)$', k, re.I)
                    else clean(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, str):
        value = re.sub(r'(?i)\bBearer\s+[A-Za-z0-9._-]{12,}', 'Bearer [REDACTED]', value)
        value = re.sub(r'(?i)(postgres(?:ql)?://)[^\s/@]+:[^\s/@]+@', r'\1[REDACTED]@', value)
        value = re.sub(r'[A-Z]:[\\/](?:Users[\\/][^\s"<>]+|project\d+[^\s"<>]*)', '[LOCAL_PATH]', value, flags=re.I)
    return value


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def group(kind):
    if kind in ('search_logs','query_logs'): return 'LOGS'
    if 'metric' in kind: return 'METRICS'
    if 'trace' in kind: return 'TRACES'
    if any(x in kind for x in ('source', 'symbol', 'repository')): return 'CODE'
    if 'database' in kind: return 'DATABASE'
    if 'redis' in kind: return 'REDIS'
    if 'kafka' in kind: return 'KAFKA'
    return 'CONTROL'


def finding(e):
    p=e['payload'];kind=e['kind']
    if isinstance(p,dict) and 'source' in p and 'path' in p:
        return f"{p['path']} · lines {p.get('start_line','?')}–{p.get('end_line','?')}"
    if isinstance(p,list):
        if 'kafka' in kind:
            return ' · '.join(f"{x.get('topic')} / partition {x.get('partition')}: lag {x.get('lag')}" for x in p)
        if kind=='search_logs':
            errors=[x for x in p if x.get('error')]
            counts=sum(int(x.get('status',0))>=500 for x in p)
            sample=str(errors[0]['error']) if errors else 'No exception text in returned rows'
            return f'{len(p)} log rows; {counts} HTTP 5xx; {sample[:170]}'
        if kind=='get_trace':
            return f"{len(p)} traces; {sum(len(x.get('spans',[])) for x in p)} recorded spans; inspect error and service relationships"
        return f'{len(p)} recorded observations from {kind}'
    if isinstance(p,dict):
        if 'http' in p and isinstance(p['http'],list):
            rows=sorted(p['http'],key=lambda r:float(r.get('error_pct',0)),reverse=True)[:2]
            return ' · '.join(f"{r['service']}: {r.get('error_pct')}% errors, P95 {float(r.get('p95_ms',0)):.2f} ms" for r in rows)
        if 'catalog_ttl' in p: return f"Catalog TTL {p['catalog_ttl']} s; global hit ratio {p.get('hit_ratio',0):.2f}; {p.get('latency_ms',0):.2f} ms Redis latency"
        if kind=='inspect_database': return f"{len(p.get('activity',[]))} sessions; {len(p.get('locks',[]))} lock records; query counters and timing retained"
        if kind=='get_service_topology': return f"{len(p.get('nodes',[]))} service/dependency nodes; observed and configured edges distinguished"
        if 'matches' in p: return f"{len(p['matches'])} repository matches"
        return 'Recorded fields: '+', '.join(list(p)[:6])
    return str(p)[:180]


def stage(event):
    k=event['kind'].lower();p=event['payload'];phase=str(p.get('phase','')).lower()
    if 'error' in k or 'failed' in k: return 'ERROR'
    if 'repair' in k or 'resume' in k: return 'RECOVERY'
    if 'root cause' in k: return 'ROOT CAUSE'
    if 'critic' in k or 'verification' in k: return 'VERIFY'
    if 'candidate' in k or 'replay' in k or 'test' in k: return 'TEST'
    if 'patch' in k: return 'PATCH'
    if 'hypothesis' in k: return 'HYPOTHESIS'
    if 'evidence' in k: return 'EVIDENCE'
    if 'triage' in k or phase=='triage': return 'TRIAGE'
    if 'plan' in k or 'plan' in phase: return 'PLAN'
    if 'tool' in k: return 'TOOL'
    if 'report' in k: return 'REPORT'
    return 'RUNTIME'


def main():
    assert digest(SOURCE.read_bytes())==SEALED, 'Frozen first result changed'
    suite=read(SOURCE);r=next(r for r in suite['results'] if r['run_id']==RID)
    incident=r['recorded_incident'];iid=r['incident_id'];ledger=r['ledger']
    assert incident['investigation_run']==RID and incident['id']==iid
    for family in ('evidence','patches','tool_calls'):
        assert all(str(x['run_id'])==RID and str(x['incident_id'])==iid for x in ledger[family])
    output_files={}
    def write(name,value):
        path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True)
        data=json.dumps(clean(value),ensure_ascii=False,separators=(',',':')).encode()
        path.write_bytes(data);output_files[name]={'sha256':digest(data),'bytes':len(data)}
    evidence=[]
    supporting=set(r['diagnosis']['evidence_ids'])
    for e in ledger['evidence']:
        write('evidence/'+e['id']+'.json',e)
        evidence.append({'id':e['id'],'run_id':RID,'source':group(e['kind']),'tool':e['kind'],
            'finding':finding(e),'why': 'Cited in the root-cause proposal.' if e['id'] in supporting else
            'Recorded observation used to inspect or cross-check the incident; not by itself proof of causality.',
            'timestamp':e['collected_at'],'supporting':e['id'] in supporting})
    events=[]
    for e in incident['steps']:
        assert not e['payload'].get('run_id') or e['payload']['run_id']==RID
        write('events/'+str(e['id'])+'.json',e)
        p=e['payload'];error=p.get('error') or {}
        label=e['kind']
        detail=p.get('tool') or p.get('phase') or p.get('status') or p.get('agent') or ''
        if error: detail=error.get('error_code',error.get('code',''))+' · '+error.get('message','')
        events.append({'id':e['id'],'ts':e['ts'],'kind':e['kind'],'stage':stage(e),'detail':str(detail),
                       'actor':p.get('agent',p.get('actor','Runtime')),'run_id':RID})
    patch=ledger['patches'][0];write('patch.json',patch)
    topology=next(e for e in ledger['evidence'] if e['kind']=='get_service_topology')
    fixture=read(ROOT/r['fixture_proof'])
    release=read(ROOT/'evaluation/phase4/final-release-report.json')
    metrics=release['version']['metrics']
    demo={'schema_version':1,'mode':'RECORDED DEMO','live':False,'model':suite['model'],'run_id':RID,
        'incident_id':iid,'recorded_at':incident['created_at'],'status':incident['status'],
        'severity':{'label':'HIGH','basis':'Presentation severity derived from recorded order-service error rate > 90%; not a historical severity field.'},
        'signal':incident['signal'],'diagnosis':r['diagnosis'],'root_decision':incident['report']['root_cause_decision'],
        'critic':r['critic'],'report_summary':incident['report']['summary'],'symptoms':r['measured']['fault_active'],
        'windows':r['measured'],'topology':topology['payload'],'topology_evidence_id':topology['id'],
        'fault_observation':{'observed_at':fixture['samples'][0]['at'],'scenario':r['scenario'],'fixture_valid':r['fixture_valid'],
             'triggered_at':None,'note':'Operator fixture verified the active fault before this incident. Exact trigger timestamp was not persisted; no synthetic trigger event is added.'},
        'events':events,'evidence':evidence,'patch':{k:patch[k] for k in ('id','origin','status')},
        'benchmark':{'id':suite['benchmark_id'],'version':'V4.1 Benchmark','metrics':metrics,'frozen_test_count':189},
        'provenance':{'source':SOURCE.relative_to(ROOT).as_posix(),'sha256':SEALED,'selection':'One complete first-release code_exception run. No cross-run evidence or patches.'}}
    write('demo.json',demo)
    comparison=read(ROOT/'evaluation/phase4/comparison.json')
    versions=comparison['versions']+[release['version']]
    for v in versions:
        for trial in v['results']:
            rid=trial.get('run_id');p=ROOT/'evaluation/runs'/f'{rid}.json'
            if p.exists():
                record=read(p)
                write('history/'+rid+'.json',{'trial':trial,'events':record.get('steps',[]),'evidence':record.get('evidence',[]),
                    'patches':record.get('patches',[]),'critic':record.get('critic'),'live':False,'display_mode':'RECORDED RUN'})
        # Keep every outcome, but don't load per-tool classification lists on the first screen.
        v['results']=[{k:val for k,val in x.items() if k!='efficiency'} for x in v['results']]
    write('evaluation.json',{'versions':versions,'scenarios':comparison['scenarios'],'pareto':comparison['pareto'],
        'ai_only_pareto':comparison['ai_only_pareto'],'complete_workflow_ai_pareto':comparison['complete_workflow_ai_pareto'],
        'interpretation_limits':comparison['interpretation_limits'],'release_limits':release['comparison_limitations'],
        'release_in_historic_pareto':False})
    sources=[SOURCE,ROOT/r['fixture_proof'],ROOT/'evaluation/phase4/comparison.json',
             ROOT/'evaluation/phase4/final-release-report.json',ROOT/'evaluation/phase4/reliability-tests-final.json']
    manifest={'run_id':RID,'incident_id':iid,'source_sha256':{p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in sources},
              'files':output_files,'sanitization':'Public derivative: remove credential fields, bearer values, credential-bearing DSNs and personal Windows paths. Frozen originals unchanged.',
              'integrity':'Incident, evidence, tool calls and patch validated against the same run and incident IDs; events retain original ID/time/order.'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'run_id':RID,'events':len(events),'evidence':len(evidence),'files':len(output_files),'summary_bytes':output_files['demo.json']['bytes']}))


if __name__=='__main__':main()
