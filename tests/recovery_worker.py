"""Operator-only SIGKILL exercise. Model decisions are real; one error is injected by the test controller."""
import asyncio
import hashlib
import json
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from psycopg.types.json import Jsonb
from services.runtime import pool,audit_pool,redis,query
from sentinel import checkpoints,runtime_agent,runtime_tools
from sentinel.runtime_state import InvestigationState
from sentinel.evidence import summary
from sentinel.security import serial,install_masking
from sentinel.storage import migrate,usage

def snapshot(state):
    fields={k:getattr(state,k) for k in ('run_id','incident_id','active_hypotheses','validation_errors','critical_evidence','unfinished_actions')}
    fields['budgets']=state.budgets.model_dump()
    fields=serial(fields)
    return {'fields':fields,'sha256':hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()}

async def main():
    await pool.open();await audit_pool.open();await pool.wait();await migrate();install_masking()
    try:
        if sys.argv[1]=='start':
            iid=str(uuid.uuid4())
            await query("INSERT INTO incidents(id,status,signal,controlled_recovery) VALUES(%s,'test',%s,false)",
                (iid,Jsonb(serial({'source':'operator recovery exercise; no scenario label','signals':await summary(20)}))))
            original=runtime_agent.Runner.save
            async def checkpoint_then_wait(self,phase=None):
                await original(self,phase)
                state=self.state
                if state.active_hypotheses and state.critical_evidence and not state.data.get('crash_exercise_prepared'):
                    state.data['crash_exercise_prepared']=True
                    async def persist(): await original(self)
                    result=await runtime_tools.execute(state,'get_code_symbol',{'path':'services/pricing.py','symbol':'recovery_exercise_absent_symbol'},
                        'recovery-controller-error',runtime_tools.NAMES,persist,actor='RecoveryTestController')
                    assert result['error']['error_code']=='SYMBOL_NOT_FOUND'
                    state.recent_results.append({'tool':'get_code_symbol','origin':'RecoveryTestController','output':result})
                    await original(self)
                    print(json.dumps({'event':'READY_FOR_SIGKILL',**snapshot(state)}),flush=True)
                    await asyncio.Future()
            runtime_agent.Runner.save=checkpoint_then_wait
            await runtime_agent.investigate_runtime(iid,'HYBRID_V4_1')
            raise RuntimeError('Run ended before crash checkpoint')
        else:
            rid=sys.argv[2]
            saved=await checkpoints.load(rid);state=InvestigationState.model_validate(saved['payload'])
            print(json.dumps({'event':'RESTORED_BEFORE_RESUME',**snapshot(state)}),flush=True)
            await runtime_agent.investigate_runtime(state.incident_id,'HYBRID_V4_1',rid)
            run=await query('SELECT status,error FROM investigation_runs WHERE id=%s',(rid,),one=True)
            current=await checkpoints.load(rid)
            print(json.dumps(serial({'event':'RESUME_FINISHED','run_id':rid,'incident_id':state.incident_id,'run':run,
                'phase':current['phase'],'resume_count':current['payload']['resume_count'],'usage':await usage(state.incident_id)})),flush=True)
    finally:
        await pool.close();await audit_pool.close();await redis.aclose()

if __name__=='__main__': asyncio.run(main())
