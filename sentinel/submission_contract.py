"""Bounded output contract; no changes to root categories or scoring semantics."""
from typing import Annotated
from pydantic import Field
from sentinel.hybrid_tools import RootCauseDecision, SignalAssessment, EvidenceID
from sentinel.contracts import CodeLocation

ShortFinding=Annotated[str,Field(max_length=160)]
ShortUncertainty=Annotated[str,Field(max_length=120)]

class CompactSignalAssessment(SignalAssessment):
    signal_id:str=Field(pattern=r'^S[1-9][0-9]*$',description='An exact signal_id from the supplied triage; never invent additional signals.')
    evidence_ids:list[EvidenceID]=Field(max_length=3)
    explanation:str=Field(max_length=120)

class CompactRootCauseDecision(RootCauseDecision):
    hypothesis:str=Field(max_length=240)
    root_cause:str=Field(min_length=10,max_length=550)
    evidence_ids:list[EvidenceID]=Field(min_length=2,max_length=8)
    code_locations:list[CodeLocation]=Field(max_length=4)
    reasoning_summary:str=Field(max_length=450)
    recommended_fix:str=Field(max_length=400)
    remaining_uncertainty:list[ShortUncertainty]=Field(max_length=3)
    supporting_evidence:list[EvidenceID]=Field(min_length=2,max_length=6,
        description=RootCauseDecision.model_fields['supporting_evidence'].description)
    contradicting_evidence:list[EvidenceID]=Field(max_length=4,
        description=RootCauseDecision.model_fields['contradicting_evidence'].description)
    deterministic_signals:list[CompactSignalAssessment]=Field(max_length=16,
        description='Assess ONLY supplied triage signals; [] when triage has none. Each explanation is one short sentence.')
    llm_findings:list[ShortFinding]=Field(max_length=3)

OUTPUT_CONTRACT='''Use compact JSON and concise English. The provider output limit is 2500 tokens.
Aim below 1400 tokens for a complete submission; every required field must fit.
Do not repeat the same explanation across hypothesis, root_cause, reasoning_summary and findings.
Copy only the real triage S-number IDs into deterministic_signals; use [] if there are no signals.
Use bare evidence IDs. Source snippets, SQL text and log transcripts belong in evidence tools, not in this JSON.
If a response was cut off, rewrite a SHORTER complete object; do not merely append to or reproduce the long prefix.
Preserve the causal claim, actual supporting citations and uncertainty. Do not manufacture findings to fill fields.
'''
