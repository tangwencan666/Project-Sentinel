"""Forensic aggregation of first-run receipts; no scoring or prompt changes."""
from collections import Counter
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    suite=json.loads((ROOT/'evaluation/results/v3.1-first-controlled.json').read_text(encoding='utf-8'))
    cases=[]
    for row in suite['results']:
        if not row.get('ledger'): continue
        tools=row['ledger'].get('tool_calls',[]);events=row.get('recorded_incident',{}).get('steps',[])
        contexts=[s['payload'] for s in events if s['kind']=='Context Rebuilt']
        calls=row['ledger']['usage']['calls']
        latencies=[(c.get('diagnostics') or {}).get('latency_seconds') for c in calls if c.get('agent')!='Evaluator']
        provider_seconds=sum(latencies) if latencies and all(isinstance(t,(int,float)) for t in latencies) else None
        submitted=[t for t in tools if t['tool_name']=='submit_root_cause_decision']
        cases.append({'scenario':row['scenario'],'incident_id':row['incident_id'],
            'workflow_completed':row.get('workflow_completed'),'error':row.get('error'),
            'hypotheses':row['ledger'].get('hypotheses',[]),'submission_attempts':len(submitted),
            'last_context_control':contexts[-1] if contexts else None,
            'tool_errors':[{k:t.get(k) for k in ('tool_name','arguments','error')} for t in tools if t.get('error')],
            'last_eight_tools':[{k:t.get(k) for k in ('tool_name','arguments','status')} for t in tools[-8:]],
            'provider_finish_reasons':dict(Counter((c.get('diagnostics') or {}).get('finish_reason') or 'unknown' for c in calls)),
            'provider_transport_failures':sum(c['status']=='failed' for c in calls),
            'workflow_seconds':row.get('duration_seconds'),
            'provider_seconds':provider_seconds,
            'non_provider_workflow_seconds':row['duration_seconds']-provider_seconds if row.get('duration_seconds') is not None and provider_seconds is not None else None,
            'timing_scope':'Non-provider time includes tools, serialization, checkpoints, supervision and any recovery waits; not all attributed to redaction.',
            'schema_repairs':sum(s['kind']=='Schema Repair' for s in events),
            'circuit_breakers':sum((t.get('error') or {}).get('error_code')=='CIRCUIT_BREAKER' for t in tools),
            'hypothesis_without_submission':bool(row['ledger'].get('hypotheses')) and not submitted})
    output={'suite_completed':suite['completed'],'cases':cases,
        'interpretation':'A stored hypothesis is not a final diagnosis and is never promoted to a scored success. Convergence can fail even with zero schema/tool protocol failures.'}
    (ROOT/'evaluation/phase4/v3.1-runtime-forensics.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps([{k:c[k] for k in ('scenario','workflow_completed','submission_attempts','hypothesis_without_submission')} for c in cases]))
if __name__=='__main__': main()
