"""Explicit remediation eligibility before any candidate generation."""
from typing import Literal
from pydantic import Field
from .contracts import Strict
from .generic_patching import PROFILES

class Eligibility(Strict):
    action:Literal['CODE_PATCH','CONFIG_CHANGE','INFRA_REMEDIATION','NO_AUTOMATIC_REMEDIATION']
    code_path:str|None=None
    rationale:str=Field(max_length=400)
    required_validation:list[str]=Field(max_length=5)

class SourceReplacement(Strict):
    source:str=Field(min_length=1,max_length=8000,description='Complete model-written source for the one approved pure business module. No diff headers or displayed line numbers.')

def enforce_eligibility(value,diagnosis):
    result=Eligibility.model_validate(value).model_dump()
    result['automatic_execution']=False
    if result['action']=='CODE_PATCH':
        cited={c['path'] for c in diagnosis.get('code_locations',[])}
        if diagnosis.get('category')=='UNKNOWN' or diagnosis.get('patch_decision')!='CODE_PATCH' or result['code_path'] not in cited or result['code_path'] not in PROFILES:
            result.update(action='NO_AUTOMATIC_REMEDIATION',code_path=None,
                policy_rejection='Code patch requires a non-UNKNOWN diagnosis and a cited supported business source path.')
    else: result['code_path']=None
    return result
