"""Actual API, DB authorization and secret-boundary audit; never print secret contents."""
from datetime import datetime,timezone
import argparse
import json
from pathlib import Path
import subprocess
import urllib.request
import urllib.error
ROOT=Path(__file__).resolve().parents[1]
PROGRAM='''
import asyncio,json
import psycopg
from sentinel.security import settings
from sentinel.evidence import READ_DSN
from services.runtime import pool,query
async def main():
    key=settings().get('LLM_API_KEY');assert key
    await pool.open();await pool.wait();findings={}
    try:
        for table in ('incidents','tool_calls','evidence_items','hypotheses','agent_steps','llm_calls','ai_patches','evaluations','recovery_checks','context_measurements','investigation_checkpoints','runtime_tool_receipts'):
            row=await query('SELECT count(*) n FROM '+table+' t WHERE strpos(row_to_json(t)::text,%s)>0',(key,),one=True)
            findings[table]=row['n']
        markers=await query("SELECT e.kind,count(*) n FROM evidence_items e JOIN investigation_runs r ON r.id=e.run_id WHERE r.mode IN ('HYBRID_V3_1','HYBRID_V4','HYBRID_V4_1') AND (strpos(e.payload::text,'ground_truth_root_cause')>0 OR strpos(e.payload::text,'scenario_id')>0) GROUP BY e.kind")
        fixture_labels=await query("SELECT p.origin,count(*) n FROM ai_patches p JOIN investigation_runs r ON r.id=p.run_id WHERE r.mode IN ('RELIABILITY_TEST','TEST') GROUP BY p.origin")
        denied={}
        async with await psycopg.AsyncConnection.connect(READ_DSN,autocommit=True) as conn:
            for table in ('evaluations','investigation_checkpoints','llm_calls'):
                try: await conn.execute('SELECT * FROM '+table+' LIMIT 0');denied[table]=False
                except psycopg.errors.InsufficientPrivilege: denied[table]=True
        print(json.dumps({'secret_rows_by_table':findings,'truth_marker_matches':markers,'investigator_role_denied':denied,
            'historical_test_artifact_labels':fixture_labels,'label_note':'Earlier component-boundary tests used the shared AI label. Run mode RELIABILITY_TEST identifies them as fixtures and excludes them from benchmarks; new artifacts carry TEST_FIXTURE explicitly.'}))
    finally: await pool.close()
asyncio.run(main())
'''

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',default='adversarial-audit-final.json');a=p.parse_args()
    assert Path(a.output).name==a.output
    output=ROOT/'evaluation/phase4'/a.output
    if output.exists(): raise FileExistsError('Retain previous audit evidence')
    checks=[]
    def request(path,method='GET',body=None,headers=None):
        req=urllib.request.Request('http://127.0.0.1:18082/api'+path,method=method,
            data=json.dumps(body).encode() if body is not None else None,headers={**({'Content-Type':'application/json'} if body is not None else {}),**(headers or {})})
        try:
            with urllib.request.urlopen(req,timeout=40) as f:return f.status,f.read()
        except urllib.error.HTTPError as exc:return exc.code,exc.read()
    before=json.loads(request('/overview')[1])
    code,_=request('/traffic/false','POST',headers={'Origin':'https://attacker.invalid'})
    after=json.loads(request('/overview')[1]);checks.append({'attack':'Cross-origin mutation','status':code,'passed':code==403 and before['traffic_enabled']==after['traffic_enabled']})
    code,_=request('/overview',headers={'Host':'attacker.invalid'});checks.append({'attack':'Untrusted Host','status':code,'passed':code==400})
    for mode in ('HYBRID_V3_1','HYBRID_V4'):
        code,_=request('/incidents','POST',{'mode':mode});checks.append({'attack':'Frozen runtime dispatch '+mode,'status':code,'passed':code==409})
    recovery=json.loads((ROOT/'evaluation/phase4/crash-resume-followup.json').read_text(encoding='utf-8'))
    iid=recovery['result']['incident_id'];incident=json.loads(request('/incidents/'+iid)[1]);patch=incident['report']['patch']
    code,_=request('/incidents/'+iid+'/deploy','POST',{'sha256':patch['sha256']})
    checks.append({'attack':'Generic candidate live deployment','status':code,'passed':code==409})
    program=subprocess.run(['docker','compose','exec','-T','sentinel','python','-'],input=PROGRAM,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=True,timeout=120)
    result=json.loads(program.stdout)
    config={}
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k,v=line.split('=',1);config[k.strip()]=v.strip().strip('"').strip("'")
    secret=config.get('LLM_API_KEY','').encode();logs=subprocess.run(['docker','compose','logs','--no-color','sentinel'],cwd=ROOT,capture_output=True,check=True).stdout
    result.update(api_checks=checks,at=datetime.now(timezone.utc).isoformat(),sentinel_log_secret_match=bool(secret and secret in logs),
        scope='Actual capability, API and database boundaries; exact secret/field-marker scan is not proof against all semantic exfiltration. Model injection probes and subprocess limits are separate artifacts.')
    result['passed']=all(c['passed'] for c in checks) and not any(result['secret_rows_by_table'].values()) and not result['truth_marker_matches'] and all(result['investigator_role_denied'].values()) and not result['sentinel_log_secret_match']
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');output.chmod(0o444)
    print(json.dumps(result,ensure_ascii=True))
    if not result['passed']: raise SystemExit(1)
if __name__=='__main__':main()
