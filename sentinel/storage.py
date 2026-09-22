import uuid
from psycopg.types.json import Jsonb
from services.runtime import query
from .security import serial

DDL=[
 "CREATE TABLE IF NOT EXISTS context_measurements(id bigserial PRIMARY KEY, run_id uuid, agent text, raw_estimated_tokens bigint, compressed_estimated_tokens bigint, estimated boolean DEFAULT true, created_at timestamptz DEFAULT now())",
 "ALTER TABLE context_measurements ADD COLUMN IF NOT EXISTS telemetry jsonb",
 "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS controlled_recovery boolean DEFAULT false",
 "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS mode text DEFAULT 'AI'",
 "ALTER TABLE incidents ADD COLUMN IF NOT EXISTS investigation_run uuid",
 "CREATE TABLE IF NOT EXISTS investigation_runs(id uuid PRIMARY KEY, incident_id uuid REFERENCES incidents(id), mode text, status text, started_at timestamptz DEFAULT now(), finished_at timestamptz, error jsonb)",
 "CREATE TABLE IF NOT EXISTS tool_calls(id uuid PRIMARY KEY, external_id text, incident_id uuid REFERENCES incidents(id), run_id uuid REFERENCES investigation_runs(id), agent text, tool_name text, arguments jsonb, started_at timestamptz DEFAULT now(), finished_at timestamptz, status text, result_summary text, evidence_ids jsonb, error jsonb)",
 "CREATE TABLE IF NOT EXISTS evidence_items(id text PRIMARY KEY, incident_id uuid REFERENCES incidents(id), run_id uuid REFERENCES investigation_runs(id), tool_call_id uuid REFERENCES tool_calls(id), kind text, collected_at timestamptz DEFAULT now(), payload jsonb NOT NULL)",
 "CREATE TABLE IF NOT EXISTS hypotheses(id text PRIMARY KEY, incident_id uuid REFERENCES incidents(id), run_id uuid REFERENCES investigation_runs(id), status text, payload jsonb, updated_at timestamptz DEFAULT now())",
 "CREATE TABLE IF NOT EXISTS llm_calls(id uuid PRIMARY KEY, incident_id uuid REFERENCES incidents(id), run_id uuid REFERENCES investigation_runs(id), agent text, model text, started_at timestamptz DEFAULT now(), finished_at timestamptz, status text, input_tokens bigint, output_tokens bigint, total_tokens bigint, estimated_cost numeric, pricing jsonb, error jsonb)",
 "ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS request_estimated_tokens bigint",
 "ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS diagnostics jsonb",
 "ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS logical_request_id text",
 "ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS request_digest text",
 "ALTER TABLE llm_calls ADD COLUMN IF NOT EXISTS response_payload jsonb",
 "CREATE INDEX IF NOT EXISTS llm_logical_request ON llm_calls(run_id,logical_request_id)",
 "CREATE TABLE IF NOT EXISTS runtime_tool_receipts(tool_call_id uuid PRIMARY KEY REFERENCES tool_calls(id), run_id uuid REFERENCES investigation_runs(id), external_id text, payload jsonb NOT NULL)",
 "CREATE UNIQUE INDEX IF NOT EXISTS runtime_receipt_external ON runtime_tool_receipts(run_id,external_id) WHERE external_id IS NOT NULL",
 "CREATE TABLE IF NOT EXISTS ai_patches(id uuid PRIMARY KEY, incident_id uuid REFERENCES incidents(id), run_id uuid REFERENCES investigation_runs(id), origin text CHECK(origin IN ('HUMAN','RULE_BASED','AI_GENERATED')), status text, artifact jsonb, created_at timestamptz DEFAULT now())",
 "DO $$ BEGIN IF EXISTS(SELECT 1 FROM pg_constraint WHERE conname='ai_patches_origin_check' AND position('TEST_FIXTURE' in pg_get_constraintdef(oid))=0) THEN ALTER TABLE ai_patches DROP CONSTRAINT ai_patches_origin_check; ALTER TABLE ai_patches ADD CONSTRAINT ai_patches_origin_check CHECK(origin IN ('HUMAN','RULE_BASED','AI_GENERATED','TEST_FIXTURE')); END IF; END $$",
 "CREATE INDEX IF NOT EXISTS tool_calls_run ON tool_calls(run_id)",
 "CREATE INDEX IF NOT EXISTS evidence_run ON evidence_items(run_id)",
 "CREATE INDEX IF NOT EXISTS steps_incident ON agent_steps(incident_id,id)",
 "CREATE TABLE IF NOT EXISTS evaluations(id uuid PRIMARY KEY, incident_id uuid REFERENCES incidents(id), run_id uuid REFERENCES investigation_runs(id), scenario_id text, mode text, result jsonb, created_at timestamptz DEFAULT now())",
 "CREATE TABLE IF NOT EXISTS recovery_checks(run_id uuid PRIMARY KEY REFERENCES investigation_runs(id), incident_id uuid REFERENCES incidents(id), status text, payload jsonb, created_at timestamptz DEFAULT now(), finished_at timestamptz)",
 "CREATE TABLE IF NOT EXISTS investigation_checkpoints(run_id uuid PRIMARY KEY REFERENCES investigation_runs(id), phase text NOT NULL, payload jsonb NOT NULL, updated_at timestamptz DEFAULT now())",
]

async def migrate():
    for statement in DDL: await query(statement)

async def event(incident_id,kind,payload,agent='Supervisor',run_id=None):
    return await query('INSERT INTO agent_steps(incident_id,kind,payload) VALUES(%s,%s,%s) RETURNING id',
        (incident_id,kind,Jsonb(serial({'agent':agent,'run_id':str(run_id) if run_id else None,**payload}))),one=True)

async def evidence_for(incident_id,run_id):
    return await query('SELECT * FROM evidence_items WHERE incident_id=%s AND run_id=%s ORDER BY collected_at',(incident_id,run_id))

async def usage(incident_id=None,include_calls=True):
    columns='c.*' if include_calls else 'c.status,c.input_tokens,c.output_tokens,c.total_tokens,c.estimated_cost'
    rows=await query("SELECT "+columns+" FROM llm_calls c LEFT JOIN investigation_runs r ON r.id=c.run_id WHERE (%s::uuid IS NULL OR c.incident_id=%s) AND (%s::uuid IS NOT NULL OR coalesce(r.mode,'') NOT IN ('RELIABILITY_TEST','TEST')) ORDER BY c.started_at",(incident_id,incident_id,incident_id))
    successful=[r for r in rows if r['status']=='succeeded']
    return {'llm_calls':len(rows),'successful_calls':len(successful),'input_tokens':sum(r['input_tokens'] for r in successful) if successful and all(r['input_tokens'] is not None for r in successful) else None,'output_tokens':sum(r['output_tokens'] for r in successful) if successful and all(r['output_tokens'] is not None for r in successful) else None,'total_tokens':sum(r['total_tokens'] for r in successful) if successful and all(r['total_tokens'] is not None for r in successful) else None,'estimated_cost':sum(r['estimated_cost'] for r in successful) if successful and all(r['estimated_cost'] is not None for r in successful) else None,'usage_source':'provider_reported','cost_source':'configured_prices_only','calls':serial(rows) if include_calls else None}
