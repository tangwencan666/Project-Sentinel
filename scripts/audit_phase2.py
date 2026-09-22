"""Read-only repository/credential audit. Never prints credential values or matches."""
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime,timezone

root=Path(__file__).resolve().parents[1]
files=subprocess.check_output(['rg','--files','--hidden','-g','!.git/**','-g','!.env','-g','!**/__pycache__/**'],cwd=root,text=True).splitlines()
keywords=re.compile(r'mock|fake|hardcoded|demo|sample|TODO|FIXME',re.I)
hits=[]
for name in files:
    if name.replace('\\','/')=='docs/phase2-audit.json': continue  # Avoid recursively scanning the previous scanner output.
    file=root/name
    try: content=file.read_text(encoding='utf-8-sig')
    except (UnicodeError,OSError): continue
    for number,line in enumerate(content.splitlines(),1):
        words=sorted(set(m.group(0).lower() for m in keywords.finditer(line)))
        if words: hits.append({'file':name.replace('\\','/'),'line':number,'keywords':words})

program='''
import asyncio,json
from sentinel.security import settings
from services.runtime import pool,query
async def main():
    key=settings().get('LLM_API_KEY')
    if not key: raise RuntimeError('credential scan requires configured key')
    await pool.open()
    findings={}
    for table in ('incidents','tool_calls','evidence_items','hypotheses','agent_steps','llm_calls','ai_patches','evaluations','recovery_checks'):
        row=await query('SELECT count(*) n FROM '+table+' t WHERE strpos(row_to_json(t)::text,%s)>0',(key,),one=True)
        findings[table]=row['n']
    await pool.close()
    print(json.dumps(findings))
asyncio.run(main())
'''
scan=subprocess.run(['docker','compose','exec','-T','sentinel','python','-'],input=program,text=True,cwd=root,capture_output=True,check=True)
database_findings=json.loads(scan.stdout)
cfg={}
for line in (root/'.env').read_text(encoding='utf-8-sig').splitlines():
    if '=' in line and not line.lstrip().startswith('#'):
        name,value=line.split('=',1);cfg[name.strip()]=value.strip().strip('"\'')
key=cfg.get('LLM_API_KEY')
repository_findings=[]
if key:
    for name in files:
        if key.encode() in (root/name).read_bytes(): repository_findings.append(name)
logs=subprocess.run(['docker','compose','logs','--no-color','sentinel'],cwd=root,capture_output=True,check=True).stdout
report={'at':datetime.now(timezone.utc).isoformat(),'files_checked':len(files),'keyword_hits':hits,'credential_value_never_printed':True,'credential_scan':{'configured':bool(key),'repository_files':repository_findings,'database_rows_by_table':database_findings,'sentinel_logs_match':bool(key and key.encode() in logs)},'scope':'literal current provider secret; pattern/redaction behavior covered by tests; not a proof of all possible future leaks'}
(root/'docs/phase2-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'files_checked':len(files),'keyword_hit_count':len(hits),'credential_scan':report['credential_scan']},ensure_ascii=True))
