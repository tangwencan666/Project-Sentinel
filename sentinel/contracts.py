from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Hypothesis(Strict):
    hypothesis_id:str=Field(pattern=r'^H-[a-zA-Z0-9_-]{1,40}$')
    status:Literal['CREATED','UPDATED','REJECTED']
    hypothesis:str=Field(max_length=2000)
    affected_service:str
    evidence_ids:list[str]
    reasoning_summary:str=Field(max_length=1600)
    next_evidence_needed:str=Field(max_length=1200)

class CodeLocation(Strict):
    path:str
    start_line:int=Field(ge=1)
    end_line:int=Field(ge=1)

class Diagnosis(Strict):
    hypothesis:str
    affected_service:str
    root_cause:str=Field(min_length=10,max_length=2500)
    category:Literal['DATABASE_SLOW_QUERY','DB_POOL_EXHAUSTION','N_PLUS_ONE','CACHE_MISS','CONSUMER_LAG','DOWNSTREAM_TIMEOUT','RETRY_AMPLIFICATION','CODE_EXCEPTION','UNKNOWN']
    evidence_ids:list[str]=Field(min_length=2)
    code_locations:list[CodeLocation]
    reasoning_summary:str=Field(max_length=1800)
    recommended_fix:str=Field(max_length=1800)
    remaining_uncertainty:list[str]
    patch_decision:Literal['CODE_PATCH','NO_CODE_PATCH']

class Critique(Strict):
    verdict:Literal['VERIFIED','PARTIALLY_VERIFIED','REJECTED']
    evidence_ids:list[str]=Field(min_length=1)
    verification_summary:str=Field(max_length=2200)
    alternative_explanations:list[str]
    regression_risks:list[str]
    test_sufficiency:str

def check_citations(ids,evidence,min_kinds=1):
    lookup={e['id']:e for e in evidence}
    if not ids or any(i not in lookup for i in ids): raise ValueError('unknown or missing evidence ID in this investigation run')
    if len({lookup[i]['kind'] for i in ids})<min_kinds: raise ValueError('independent evidence sources required')

def validate_diagnosis(payload,evidence):
    diagnosis=Diagnosis.model_validate(payload)
    check_citations(diagnosis.evidence_ids,evidence,2)
    code=[e['payload'] for e in evidence if e['kind'] in ('read_source_file','get_code_symbol','get_code_context')]
    for location in diagnosis.code_locations:
        if location.end_line<location.start_line: raise ValueError('invalid line range')
        if not any(c['path']==location.path and c['start_line']<=location.start_line<=location.end_line<=c['end_line'] for c in code): raise ValueError('code citation not read by investigator')
    if diagnosis.patch_decision=='CODE_PATCH' and not diagnosis.code_locations: raise ValueError('code patch requires source evidence')
    return diagnosis
