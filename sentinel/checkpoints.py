"""Durable stage and tool-batch cursors. Single-process runner owns each run."""
from psycopg.types.json import Jsonb
from services.runtime import query
from .security import serial
from .storage import event

STATES={'CREATED','TRIAGE','PLANNING','INVESTIGATING','ROOT_CAUSE','PATCHING','TESTING','VERIFYING','COMPLETED','FAILED'}

async def save(incident_id,run_id,phase,payload):
    if phase not in STATES: raise ValueError('invalid checkpoint phase')
    await query('INSERT INTO investigation_checkpoints(run_id,phase,payload) VALUES(%s,%s,%s) ON CONFLICT(run_id) DO UPDATE SET phase=excluded.phase,payload=excluded.payload,updated_at=now()',
                (run_id,phase,Jsonb(serial(payload))))
    await event(incident_id,'Checkpoint',{'phase':phase,'tool_cursor':payload.get('cursor',0)},run_id=run_id)

async def load(run_id):
    return await query('SELECT * FROM investigation_checkpoints WHERE run_id=%s',(run_id,),one=True)

async def previous_tool(run_id,external_id):
    row=await query("SELECT * FROM tool_calls WHERE run_id=%s AND external_id=%s AND status IN ('succeeded','failed') ORDER BY started_at DESC LIMIT 1",(run_id,external_id),one=True)
    if not row: return None
    if row['status']=='failed': return {'tool_call_id':str(row['id']),'evidence_ids':[],'error':row['error'],'resumed_from_ledger':True}
    evidence=await query('SELECT payload FROM evidence_items WHERE tool_call_id=%s ORDER BY collected_at',(row['id'],))
    if evidence: result=evidence[0]['payload']
    elif row['tool_name']=='record_hypothesis': result={'hypothesis_id':row['arguments']['hypothesis_id'],'status':row['arguments']['status']}
    else: return None
    return {'tool_call_id':str(row['id']),'evidence_ids':row['evidence_ids'],'result':result,'resumed_from_ledger':True}
