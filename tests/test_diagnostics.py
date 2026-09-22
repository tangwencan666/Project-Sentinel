from sentinel.diagnostics import project

def test_operator_projection_omits_private_request_envelope_and_incident_payload():
    data=project({'phase':'INVESTIGATING','payload':{'version':'4.1','budgets':{'limits':{'correction':12},'used':{'correction':3}},
        'data':{'investigator_request':{'messages':'NEVER_EXPORT_REQUEST'},'signal':{'private':'NEVER_EXPORT_INCIDENT'}},
        'unfinished_actions':[{'function':{'name':'read_evidence','arguments':'NEVER_EXPORT_ARGS'}}]}},[],[],[])
    import json
    assert 'NEVER_EXPORT' not in json.dumps(data)
    assert data['budgets']==[{'name':'correction','limit':12,'used':3,'remaining':9}]
    assert data['unfinished_tools']==['read_evidence']

def test_missing_legacy_diagnostics_stays_unknown():
    data=project(None,[],[],[])
    assert data['legacy_state_unavailable'] and data['round'] is None and data['resume_count'] is None
