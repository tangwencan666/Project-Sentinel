"""Conservative structural verification, independent of the LLM's semantic verdict."""
import re
from .context_engineering import independent_sources


def patch_risk(diff):
    files=re.findall(r'^\+\+\+ b/(.+)$',diff,re.M)
    changes=[l for l in diff.splitlines() if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
    text='\n'.join(changes).lower()
    factors={'file_count':len(files),'changed_lines':len(changes),
        'database':bool(re.search(r'\bsql\b|\bselect\b|\binsert\b|\balter\b|\bdelete\b|\bquery\(',text)),
        'concurrency':bool(re.search(r'async|await|thread|lock|semaphore|gather',text)),
        'infrastructure':any(f.startswith(('infra/','compose')) for f in files),
        'api_contract':bool(re.search(r'^[+-].*(?:def |@app\.|BaseModel)',text,re.M))}
    high=any(factors[k] for k in ('database','concurrency','infrastructure','api_contract')) or len(files)>2 or len(changes)>80
    level='HIGH' if high else 'MEDIUM' if len(changes)>12 or len(files)>1 else 'LOW'
    return {'level':level,'factors':factors,'automatic_apply_allowed':False,
            'policy':'Every AI patch requires explicit operator Apply; HIGH is never automatically applied.'}


def deterministic_verify(decision,evidence,triage,topology,patch,recovery):
    checks=[];known={e['id']:e for e in evidence}
    def check(name,passed,detail): checks.append({'check':name,'status':'PASS' if passed else 'FAIL','detail':detail})
    supporting=decision.get('supporting_evidence',[])
    check('citations_exist',bool(supporting) and all(i in known for i in supporting),'Citations must belong to this run.')
    sources=independent_sources(supporting,evidence)
    check('independent_sources',len(sources)>=2,sources)
    service=decision.get('affected_service')
    # Provenance-consistent service membership is a structural check, not causal proof.
    cited_text=' '.join(str(known[i]['payload']) for i in supporting if i in known)
    check('service_observed_in_evidence_and_topology',service in topology.get('nodes',[]) and service in cited_text,
          'Affected service must occur in cited observations and topology. This does not prove causal localization.')
    assessments={a['signal_id']:a for a in decision.get('deterministic_signals',[])}
    unresolved=[]
    for signal in triage.get('signals',[]):
        assessment=assessments.get(signal['signal_id'])
        if not assessment or assessment['disposition']=='uncertain' or not assessment.get('evidence_ids') or any(i not in known for i in assessment['evidence_ids']):
            unresolved.append(signal['signal_id'])
    check('signals_addressed',not unresolved,{'unresolved_signal_ids':unresolved})
    check('no_declared_strong_conflicts',not decision.get('contradicting_evidence'),decision.get('contradicting_evidence',[]))
    check('nonempty_causal_claim',decision.get('category')!='UNKNOWN','UNKNOWN cannot be fully verified against active signals.')
    if patch:
        target=patch.get('path','services/pricing.py')
        check('patch_related',any(c['path']==target for c in decision.get('code_locations',[])),
              'Candidate path must match the source cited in the diagnosis: '+target)
        check('real_tests_passed',patch.get('candidate_test',{}).get('exit_code')==0 and patch.get('validated') is True,patch.get('candidate_test',{}))
        replay=patch.get('replay') or {}
        check('real_fault_replay',patch.get('candidate_verified') is True and replay.get('passed') is True,'Baseline failure and candidate success must both be measured.')
        check('before_after_measured',all(replay.get(w,{}).get('source')=='Measured' and replay.get(w,{}).get('requests',0)>0 for w in ('before','after')),'Sandbox HTTP measurements.')
    else:
        checks.append({'check':'code_patch_tests','status':'NOT_APPLICABLE','detail':'NO_CODE_PATCH; operational recommendation, not a code repair.'})
        check('remediation_plan',bool(decision.get('recommended_fix')),'No infrastructure changes automatically applied.')
        if recovery:
            check('before_after_measured',all(recovery.get(w,{}).get('source')=='Measured' for w in ('before','after')),'Operator restoration, not AI repair.')
    return {'status':'FAIL' if any(c['status']=='FAIL' for c in checks) else 'PASS','checks':checks,
            'scope':'deterministic integrity checks; semantic correctness still requires independent evaluation'}


def combine_verdict(review,verification):
    result=dict(review);llm=result['verdict']
    if verification['status']=='FAIL' and llm=='VERIFIED': result['verdict']='PARTIALLY_VERIFIED'
    result.update(llm_verdict=llm,deterministic_verifier=verification,
                  disagreement=llm=='VERIFIED' and verification['status']=='FAIL')
    return result
