"""Assemble first valid trials after an objectively demonstrated fixture failure.

Original suites are never overwritten; semantic failures in all other scenarios stay.
"""
import copy
from datetime import datetime,timezone
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    proof=json.loads((ROOT/'evaluation/pool-fixture-proof.json').read_text(encoding='utf-8'))
    assert proof['replacement_allowed'] and proof['source_unchanged'] and proof['image_before']==proof['image_after']
    assert not any(p['saturation_proven'] for p in proof['before']) and any(p['saturation_proven'] for p in proof['after'])
    for version,name in [('v2','v2-hybrid.json'),('v3','v3-context-optimized.json')]:
        path=ROOT/'evaluation/results'/name;original=json.loads(path.read_text(encoding='utf-8'))
        supplement=json.loads((ROOT/f'evaluation/results/{version}-pool-revalidation.json').read_text(encoding='utf-8'))
        assert original['completed'] and supplement['precondition']['saturation_proven'] and supplement['source_unchanged']
        assert original['source_sha256']==supplement['source_sha256']
        assembled=copy.deepcopy(original)
        excluded=next(r for r in original['results'] if r['scenario']=='pool_exhaustion')
        assert excluded['incident_id']==supplement['original_trial']
        assembled['results']=[supplement['result'] if r['scenario']=='pool_exhaustion' else r for r in assembled['results']]
        assembled['selection_policy']={'rule':'First valid trial per scenario. Only demonstrably inactive pool injection is replaced; wrong answers in other scenes remain.',
            'predeclared_in':'evaluation/pool-validity-investigation.json','proof':'evaluation/pool-fixture-proof.json',
            'original_suite':path.relative_to(ROOT).as_posix(),'supplement':f'evaluation/results/{version}-pool-revalidation.json',
            'excluded_incident_id':excluded['incident_id'],'original_pool_judgment':excluded['judgment'],
            'initial_root_correct':sum(r['judgment']['root_cause_correct'] for r in original['results']),
            'initial_service_correct':sum(r['service_correct'] for r in original['results'])}
        assembled['initial_finished_at']=original['finished_at'];assembled['finished_at']=datetime.now(timezone.utc).isoformat()
        output=path.with_name(path.stem+'-validated.json')
        with output.open('x',encoding='utf-8') as f:json.dump(assembled,f,ensure_ascii=False,indent=2)
        output.chmod(0o444)
        print(json.dumps({'dataset':output.name,'initial_correct':assembled['selection_policy']['initial_root_correct'],'valid_correct':sum(r['judgment']['root_cause_correct'] for r in assembled['results'])}))


if __name__=='__main__':main()
