"""Public API boundary tests using frozen real data; no provider calls."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from fastapi.testclient import TestClient
from sentinel import public_demo as public

@pytest.fixture(scope='module')
def client():
    # One stateless read-only server; verify the full archive once as in production.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('PUBLIC_DEMO_MODE','true')
        patch.setenv('DEMO_ALLOWED_HOSTS','testserver,localhost,127.0.0.1')
        with TestClient(public.create_app()) as c:yield c

@pytest.mark.parametrize('path',['/','/incident.html','/replay.html','/evidence.html','/root-cause.html','/patch.html','/evaluation.html','/architecture.html','/documentation.html','/portfolio.js','/replay.js','/portfolio.css','/favicon.ico'])
def test_public_pages_have_security_headers(client,path):
    r=client.get(path);assert r.status_code==200
    assert "script-src 'self'" in r.headers['content-security-policy']
    assert r.headers['x-content-type-options']=='nosniff'

@pytest.mark.parametrize('path',['/api/faults/code_exception','/api/incidents','/api/incidents/00000000-0000-0000-0000-000000000001/deploy','/api/provider/check','/api/traffic/false','/api/rollback','/api/tools/shell','/api/database/query','/api/config','/api/upload','/api/secrets','/api/evaluation-session/true'])
@pytest.mark.parametrize('method',['POST','PUT','PATCH','DELETE'])
def test_all_mutations_rejected_before_dispatch(client,path,method):
    before=public.read('manifest.json')
    r=client.request(method,path,json={'command':'echo forbidden','sql':'DELETE FROM incidents','model':'x'})
    assert r.status_code==403 and 'PUBLIC_DEMO_READ_ONLY' in r.text
    assert public.read('manifest.json')==before

def test_no_database_or_provider_imported_by_public_entrypoint():
    program="from sentinel.public_demo import create_app; import sys; create_app(); assert not any(x in sys.modules for x in ['services.runtime','sentinel.provider','sentinel.storage','sentinel.tool_registry','psycopg','redis','aiokafka'])"
    r=subprocess.run([sys.executable,'-c',program],capture_output=True,text=True)
    assert r.returncode==0,r.stderr

def test_live_entrypoint_fails_before_imports_in_public_mode():
    env={**os.environ,'PUBLIC_DEMO_MODE':'true'}
    r=subprocess.run([sys.executable,'-c','import sentinel.api'],env=env,capture_output=True,text=True)
    assert r.returncode!=0 and 'live runtime import refused' in r.stderr

def test_false_public_flag_cannot_unlock_public_factory(client,monkeypatch):
    monkeypatch.setenv('PUBLIC_DEMO_MODE','false');app=public.create_app()
    with TestClient(app) as c:
        assert c.get('/api/portfolio/config').json()['public_demo'] is True
        assert c.post('/api/incidents').status_code==403

def test_live_html_and_unknown_tools_denied(client):
    assert client.get('/live.html').status_code==403
    assert client.get('/api/tools/shell').status_code==404

def test_untrusted_host_rejected(client):
    assert client.get('/',headers={'Host':'attacker.invalid'}).status_code==400

@pytest.mark.parametrize('name',['../.env','docs/../../.env','/etc/passwd','docs/../sentinel/provider.py'])
def test_document_traversal_denied(client,name):
    assert client.get('/api/portfolio/docs',params={'name':name}).status_code==404

def test_unknown_evidence_and_events_fail(client):
    assert client.get('/api/portfolio/evidence/E-not-in-this-run').status_code==404
    assert client.get('/api/portfolio/events/999999999').status_code==404

def test_summary_is_small_and_raw_is_on_demand(client):
    r=client.get('/api/portfolio/demo');d=r.json()
    assert len(r.content)<100000
    assert all('payload' not in e for e in d['evidence'])
    assert next(e for e in d['evidence'] if e['tool']=='get_service_topology')['source']=='CONTROL'
    e=client.get('/api/portfolio/evidence/'+d['evidence'][0]['id']).json()
    assert e['run_id']==d['run_id'] and 'payload' in e

def test_same_run_integrity_and_patch_truth(client):
    d=client.get('/api/portfolio/demo').json();p=client.get('/api/portfolio/patch').json()
    assert p['run_id']==d['run_id'] and p['incident_id']==d['incident_id']
    assert p['artifact']['production_applied'] is False
    assert p['artifact']['candidate_test']['exit_code']==0
    assert p['artifact']['replay']['before']['error_pct']==100
    assert p['artifact']['replay']['after']['error_pct']==0
    for e in d['evidence']:
        raw=client.get('/api/portfolio/evidence/'+e['id']).json()
        assert raw['run_id']==d['run_id'] and raw['incident_id']==d['incident_id']

def test_original_timeline_order_errors_recovery_and_no_fake_trigger(client):
    d=client.get('/api/portfolio/demo').json();events=d['events']
    assert [e['id'] for e in events]==sorted(e['id'] for e in events)
    assert any(e['stage']=='ERROR' for e in events)
    assert any(e['stage']=='RECOVERY' for e in events)
    assert d['fault_observation']['triggered_at'] is None
    assert not any(e['kind']=='Fault Triggered' for e in events)
    for e in events:
        raw=client.get('/api/portfolio/events/'+str(e['id'])).json()
        assert raw['id']==e['id'] and raw['ts']==e['ts'] and raw['kind']==e['kind']

def test_frozen_failures_and_all_cohorts_visible(client):
    v={v['key']:v for v in client.get('/api/portfolio/evaluation').json()['versions']}
    assert len(v)==7 and v['v3']['metrics']['workflow_completed']==2
    assert v['v3.1']['metrics']['workflow_completed']==1
    assert v['v4.1']['metrics']['total_tokens']==1461870
    assert not next(r for r in v['v4.1']['results'] if r['scenario']=='retry_storm')['correct']

def test_downloads_are_actual_candidate_and_report(client):
    assert 'What is recorded' in client.get('/api/portfolio/docs',params={'name':'FINAL_STATUS.md'}).json()['content']
    assert '+    if discount is None:' in client.get('/api/portfolio/patch.diff').text
    report=client.get('/api/portfolio/report')
    assert 'NOT DEPLOYED' in report.text and 'PARTIALLY_VERIFIED' in report.text
    assert 'attachment' in report.headers['content-disposition']
    verification=client.get('/api/portfolio/verification')
    assert verification.status_code==200
    assert verification.json()['cost']['phase5_real_llm_calls']==0
    assert 'attachment' in verification.headers['content-disposition']

def test_manifest_integrity(client):
    public.verify_artifacts()
    m=client.get('/api/portfolio/provenance').json()
    assert m['source_sha256']['evaluation/results/v4.1-first-controlled.json']=='74b48f0cc7a3f341ca0a088a50054fa0c45209034d12aa4f5de46a4f1fa2c81a'

def test_modified_record_rejected(tmp_path,monkeypatch):
    (tmp_path/'demo.json').write_text('{}')
    (tmp_path/'manifest.json').write_text(json.dumps({'files':{'demo.json':{'sha256':'0'*64}}}))
    public.read.cache_clear();monkeypatch.setattr(public,'DATA',tmp_path)
    with pytest.raises(RuntimeError,match='integrity'):public.verify_artifacts()
    public.read.cache_clear()
