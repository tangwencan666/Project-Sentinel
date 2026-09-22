"""POST-investigation judge. Never imported by Investigator or its tool graph."""
import json
import uuid
from pydantic import BaseModel,ConfigDict,Field
from psycopg.types.json import Jsonb
from services.runtime import query
from .provider import complete
from .security import serial

class Judgment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    root_cause_correct:bool
    evidence_quality:int=Field(ge=0,le=2)
    explanation:str=Field(max_length=2200)

async def evaluate(incident_id,scenario_id):
    row=await query('SELECT * FROM incidents WHERE id=%s',(incident_id,),one=True)
    if not row or row['status'] in ('detected','investigating','verifying'): raise ValueError('evaluation is allowed only after investigation ends')
    run=await query('SELECT * FROM investigation_runs WHERE id=%s',(row['investigation_run'],),one=True)
    if not run or not run['finished_at']: raise ValueError('run is not terminal')
    # Truth enters this evaluator only after the above terminal-state checks.
    from .scenarios import REGISTRY
    if scenario_id not in REGISTRY: raise ValueError('unknown scenario')
    truth=REGISTRY[scenario_id]
    report=row.get('report') or {};diagnosis=report.get('diagnosis') or {}
    proposal_recovered=False
    if not diagnosis:
        # A downstream verifier failure must not erase a previously schema-validated proposal.
        proposed=await query("SELECT payload FROM agent_steps WHERE incident_id=%s AND kind='Root Cause Proposed' AND payload->>'run_id'=%s ORDER BY id DESC LIMIT 1",(incident_id,str(run['id'])),one=True)
        if proposed:
            from .contracts import Diagnosis
            diagnosis=Diagnosis.model_validate({k:v for k,v in proposed['payload'].items() if k in Diagnosis.model_fields}).model_dump()
            proposal_recovered=True
    evidence=await query('SELECT id,kind,payload FROM evidence_items WHERE run_id=%s ORDER BY collected_at',(run['id'],))
    calls=await query('SELECT count(*) n FROM tool_calls WHERE run_id=%s',(run['id'],),one=True)
    patches=await query('SELECT origin,status,artifact FROM ai_patches WHERE run_id=%s ORDER BY created_at',(run['id'],))
    generated=await query("SELECT count(*) n FROM tool_calls WHERE run_id=%s AND tool_name IN ('validate_patch','run_tests') AND arguments ? 'diff'",(run['id'],),one=True)
    judgment={'root_cause_correct':False,'evidence_quality':0,'explanation':'Investigation failed or produced no valid diagnosis.'}
    if diagnosis:
        from .agent import parse_json
        messages=[{'role':'system','content':'You are a post-investigation evaluator, isolated from investigators. Score the submitted diagnosis against immutable experimental ground truth. Correct category alone is not enough: require the causal mechanism and service to be materially correct. Accept a higher-level accurate mechanism without the injection implementation detail; reject contradictory invented mechanisms. Use the same standards for AI and rules. Evidence quality: 0 unsupported, 1 one useful source, 2 independent supporting observations. Return only JSON {"root_cause_correct":bool,"evidence_quality":0|1|2,"explanation":str}. Never produce hidden reasoning.'},{'role':'user','content':json.dumps(serial({'ground_truth':truth,'diagnosis':diagnosis,'evidence':[{'id':e['id'],'kind':e['kind'],'payload':json.dumps(e['payload'],ensure_ascii=False)[:2200]} for e in evidence]}),ensure_ascii=False)}]
        response=await complete(incident_id,run['id'],'Evaluator',messages)
        judgment=Judgment.model_validate(parse_json(response.get('content'))).model_dump()
    duration=(run['finished_at']-run['started_at']).total_seconds()
    result=serial({'scenario':scenario_id,'ground_truth':truth['ground_truth_root_cause'],'expected_service':truth['affected_service'],'mode':row['mode'],'incident_id':str(incident_id),'run_id':str(run['id']),'run_status':run['status'],'diagnosis':diagnosis or None,'critic':report.get('critic'),'judgment':judgment,'service_correct':diagnosis.get('affected_service')==truth['affected_service'],'tool_calls':calls['n'],'duration_seconds':duration,'evidence_ids':[e['id'] for e in evidence],'patch_generated':bool(patches),'patch_applied':any(s['kind']=='deployment' for s in await query('SELECT kind FROM agent_steps WHERE incident_id=%s',(incident_id,))),'tests_passed':any(p['artifact'].get('validated') for p in patches),'fault_replay_passed':any(p['artifact'].get('candidate_verified') for p in patches),'patches':[{'origin':p['origin'],'status':p['status'],'sha256':p['artifact']['sha256']} for p in patches],'error':run['error'],'scoring':'model judge after investigation; human review recommended; failures remain in denominator'})
    result.update(patch_generated=bool(patches or generated['n']),patch_requested=diagnosis.get('patch_decision')=='CODE_PATCH',patch_generation_attempts=generated['n'],measured_recovery=report.get('measured_recovery'),validated_proposal_recovered_from_audit=proposal_recovered,workflow_completed=run['status']=='completed')
    await query('INSERT INTO evaluations(id,incident_id,run_id,scenario_id,mode,result) VALUES(%s,%s,%s,%s,%s,%s)',(str(uuid.uuid4()),incident_id,run['id'],scenario_id,row['mode'],Jsonb(result)))
    return result
