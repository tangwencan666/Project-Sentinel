"""Observe operator recovery. No fault controls, experiment labels or truth access."""
import asyncio
import time
from datetime import datetime,timezone
from psycopg.types.json import Jsonb
from services.runtime import query
from .storage import event,evidence_for
from .tool_registry import execute_tool
from .security import serial

async def snapshot(incident_id,run_id):
    observed_at=datetime.now(timezone.utc).isoformat()
    ids=[]
    for name in ('query_metrics','get_service_health','inspect_database','inspect_redis','inspect_kafka'):
        result=await execute_tool(name,{},incident_id,run_id,'RecoveryObserver')
        if result.get('error'): raise ValueError('recovery observation failed: '+name)
        ids.extend(result['evidence_ids'])
    evidence=await evidence_for(incident_id,run_id)
    data={e['kind']:e['payload'] for e in evidence if e['id'] in ids}
    return serial({'source':'Measured','observed_at':observed_at,'window_seconds':20,'evidence_ids':ids,'http':data['query_metrics']['http'],'db_pool':data['get_service_health'],'database':data['inspect_database'],'redis':data['inspect_redis'],'kafka_lag':data['inspect_kafka']})

async def observe_recovery(incident_id,run_id):
    existing=await query('SELECT status,payload FROM recovery_checks WHERE run_id=%s',(run_id,),one=True)
    if existing:
        if existing['status']=='completed': return existing['payload']
        before=existing['payload']['before']
        await query("UPDATE recovery_checks SET status='awaiting_recovery' WHERE run_id=%s AND status='measuring'",(run_id,))
    else:
        before=await snapshot(incident_id,run_id)
        payload={'before':before,'after':None,'recovery_actor':'operator_experiment_runner','not_an_ai_repair':True,'causality_limit':'Operator restoration is observational support; not an AI patch or proof of a unique mechanism.'}
        await query("INSERT INTO recovery_checks(run_id,incident_id,status,payload) VALUES(%s,%s,'awaiting_recovery',%s)",(run_id,incident_id,Jsonb(payload)))
    await query("UPDATE incidents SET status='awaiting_recovery' WHERE id=%s",(incident_id,))
    await event(incident_id,'Recovery Measurement Requested',{'run_id':run_id,'before_evidence_ids':before['evidence_ids'],'minimum_clean_window_seconds':22,'not_an_ai_repair':True},'RecoveryObserver',run_id)
    deadline=time.monotonic()+110
    while time.monotonic()<deadline:
        row=await query('SELECT status,payload FROM recovery_checks WHERE run_id=%s',(run_id,),one=True)
        if row['status']=='completed':
            await query("UPDATE incidents SET status='investigating' WHERE id=%s",(incident_id,))
            return row['payload']
        await asyncio.sleep(1)
    raise TimeoutError('OPERATOR_RECOVERY_MEASUREMENT_TIMEOUT')

async def capture_after(incident_id,run_id):
    row=await query("SELECT r.*,i.investigation_run,i.status incident_status FROM recovery_checks r JOIN incidents i ON i.id=r.incident_id WHERE r.run_id=%s AND r.incident_id=%s",(run_id,incident_id),one=True)
    if not row or str(row['investigation_run'])!=str(run_id) or row['incident_status']!='awaiting_recovery': raise ValueError('no pending recovery for this run')
    if (datetime.now(timezone.utc)-row['created_at']).total_seconds()<22: raise ValueError('a complete 22-second observation window is required')
    claimed=await query("UPDATE recovery_checks SET status='measuring' WHERE run_id=%s AND status='awaiting_recovery' RETURNING run_id",(run_id,),one=True)
    if not claimed: raise ValueError('recovery measurement already captured or running')
    try:
        payload=row['payload'];payload['after']=await snapshot(incident_id,run_id)
        await query("UPDATE recovery_checks SET status='completed',payload=%s,finished_at=now() WHERE run_id=%s",(Jsonb(payload),run_id))
        await event(incident_id,'Recovery Measured',payload,'RecoveryObserver',run_id)
        return payload
    except Exception:
        await query("UPDATE recovery_checks SET status='awaiting_recovery' WHERE run_id=%s",(run_id,))
        raise
