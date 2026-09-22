"""Real DeepSeek field-repair probe against retained failures; no RCA grading."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import uuid
sys.path.insert(0,str(Path(__file__).parent))
sys.path.insert(0,'/app')
import field_repair
from psycopg.types.json import Jsonb
from services.runtime import pool,query
from sentinel.provider import complete,configuration
from sentinel.structured_output import parse_validate,mark_parse
from sentinel.submission_contract import CompactRootCauseDecision
from sentinel.runtime_state import RuntimeFailure,ToolError
from sentinel.security import serial

async def main():
    suite=json.loads(Path('/app/evaluation/phase4/v3.1.2-qualification.continued-1.json').read_text())
    assert suite['completed'] and configuration()['LLM_MODEL']=='deepseek-chat'
    await pool.open()
    result={'scope':'REAL_PROVIDER_PROTOCOL_REPAIR_ONLY_NOT_RCA_ACCURACY','maximum_repairs_per_case':2,
            'candidate_sha256':hashlib.sha256(Path(field_repair.__file__).read_bytes()).hexdigest(),'cases':[]}
    try:
        for trial in suite['results']:
            call=next(c for c in trial['ledger']['tool_calls'] if (c.get('error') or {}).get('error_code')=='FIELD_TOO_LONG')
            raw=call['arguments'];source={'artifact':'v3.1.2-qualification.continued-1.json','tool_call_id':call['id']}
            if trial['scenario']=='n_plus_one':
                # The actual terminal response that resisted both previous full-object repairs.
                cp=await query('SELECT c.payload FROM investigation_checkpoints c JOIN investigation_runs r ON r.id=c.run_id WHERE r.incident_id=%s',('13b988eb-630c-4a5a-8c12-fbfc6dadb238',),one=True)
                jobs=[j for k,j in cp['payload']['data']['structured_jobs'].items() if k.startswith('ToolRepair:') and j.get('last_error',{}).get('error_code')=='FIELD_TOO_LONG']
                raw=json.loads(jobs[-1]['messages'][1]['content'])['invalid_output']
                source={'checkpoint_incident':'13b988eb-630c-4a5a-8c12-fbfc6dadb238','kind':'terminal_failed_repair_output'}
            try: parse_validate(raw,CompactRootCauseDecision)
            except RuntimeFailure as exc: job=field_repair.prepare(raw,exc.public())
            else: raise AssertionError('Probe input must be an actual retained invalid output')
            assert job
            iid=str(uuid.uuid4());rid=str(uuid.uuid4())
            await query("INSERT INTO incidents(id,status,signal) VALUES(%s,'test',%s)",(iid,Jsonb({'source':'protocol_repair_probe','not_accuracy':True})))
            await query("INSERT INTO investigation_runs(id,incident_id,mode,status) VALUES(%s,%s,'RUNTIME_PROTOCOL_PROBE','started')",(rid,iid))
            row={'case_label':trial['scenario'],'source':source,'run_id':rid,'incident_id':iid,'attempts':[],'passed':False}
            result['cases'].append(row);feedback=None
            for attempt in range(2):
                response=await complete(iid,rid,'InvestigatorRepairProbe',field_repair.messages(job,feedback),include_metadata=True)
                attempt_row={'attempt':attempt+1,'provider':response['_runtime'],'reply':response.get('content')}
                row['attempts'].append(attempt_row)
                try:
                    value=field_repair.apply(response.get('content'),job)
                    parsed=parse_validate(value,CompactRootCauseDecision)
                    assert parsed['evidence_ids']==job['base']['evidence_ids']
                    assert parsed['affected_service']==job['base']['affected_service']
                    assert parsed['category']==job['base']['category']
                    await mark_parse(response['_runtime'])
                    row.update(passed=True,fields=[{'path':f['path'],'before_characters':f['current_characters'],
                        'after_characters':len(field_repair.value_at(parsed,f['path'])),'maximum':f['maximum_characters']} for f in job['fields']],
                        immutable_fields_preserved=True)
                    break
                except (RuntimeFailure,ValueError) as exc:
                    feedback=exc.public() if isinstance(exc,RuntimeFailure) else {'message':str(exc)}
                    await mark_parse(response['_runtime'],ToolError(error_code='SCHEMA_VALIDATION_FAILED',message=str(feedback)))
                    attempt_row['error']=feedback
            await query('UPDATE investigation_runs SET status=%s,finished_at=now() WHERE id=%s',('completed' if row['passed'] else 'failed',rid))
        result['passed']=all(c['passed'] for c in result['cases'])
    except Exception as exc:
        result.update(passed=False,runner_error=type(exc).__name__+': '+str(exc))
    finally:
        print(json.dumps(serial(result),ensure_ascii=False))
        await pool.close()

if __name__=='__main__': asyncio.run(main())
