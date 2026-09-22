"""Read-only runtime audit. Secret values and matching database payloads are never emitted."""
import json
import subprocess
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

PROGRAM='''
import asyncio,json
from sentinel.security import settings
from services.runtime import pool,query
async def main():
    key=settings().get('LLM_API_KEY')
    if not key: raise RuntimeError('configured credential required for exact-match scan')
    await pool.open()
    findings={}
    for table in ('incidents','tool_calls','evidence_items','hypotheses','agent_steps','llm_calls','ai_patches','evaluations','recovery_checks','context_measurements','investigation_checkpoints'):
        row=await query('SELECT count(*) n FROM '+table+' t WHERE strpos(row_to_json(t)::text,%s)>0',(key,),one=True)
        findings[table]=row['n']
    leaks=await query("""SELECT e.kind,count(*) n FROM evidence_items e
        JOIN investigation_runs r ON r.id=e.run_id
        WHERE r.mode IN ('HYBRID_V2','HYBRID_V3') AND
        (strpos(e.payload::text,'ground_truth_root_cause')>0 OR strpos(e.payload::text,'scenario_id')>0)
        GROUP BY e.kind""")
    await pool.close()
    print(json.dumps({'secret_rows_by_table':findings,'truth_field_evidence_matches':leaks}))
asyncio.run(main())
'''


def main():
    result=subprocess.run(['docker','compose','exec','-T','sentinel','python','-'],input=PROGRAM,
        text=True,cwd=ROOT,capture_output=True,check=True)
    data=json.loads(result.stdout)
    config={}
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            name,value=line.split('=',1);config[name.strip()]=value.strip().strip('"').strip("'")
    secret=config.get('LLM_API_KEY','').encode()
    logs=subprocess.run(['docker','compose','logs','--no-color','sentinel'],cwd=ROOT,capture_output=True,check=True).stdout
    data.update(at=datetime.now(timezone.utc).isoformat(),sentinel_logs_secret_match=bool(secret and secret in logs),
        scope='Literal configured secret and truth-field markers; not a proof of all possible semantic leaks. No matching payload printed.')
    data['passed']=not any(data['secret_rows_by_table'].values()) and not data['truth_field_evidence_matches'] and not data['sentinel_logs_secret_match']
    (ROOT/'evaluation/runtime-audit.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(data))
    if not data['passed']: raise SystemExit(1)


if __name__=='__main__': main()
