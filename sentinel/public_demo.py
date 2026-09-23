"""Read-only portfolio server. No storage, provider, tool or business-runtime imports."""
import hashlib
import json
import os
import uuid
from functools import lru_cache
from pathlib import Path
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'portfolio/data'
router = APIRouter(prefix='/api/portfolio')

@lru_cache(maxsize=8)
def read(name):
    path = DATA / name
    if not path.is_file(): raise HTTPException(404, 'Recorded artifact unavailable')
    return json.loads(path.read_text(encoding='utf-8'))

def enabled(value): return str(value).lower() in ('1', 'true', 'yes')

@router.get('/config')
def config():
    public = enabled(os.getenv('PUBLIC_DEMO_MODE', 'true'))
    live = not public and enabled(os.getenv('LIVE_AI_ENABLED', 'false'))
    return {'default_mode': 'RECORDED DEMO', 'public_demo': public, 'live_enabled': live,
            'live_url': '/live.html' if not public else None,
            'message': 'Live AI investigation is disabled in the public demo. Run Sentinel locally to enable live investigation.' if public else
            'Local Live AI requires explicit LIVE_AI_ENABLED=true and configured provider credentials.'}

@router.get('/demo')
def demo(): return read('demo.json')

@router.get('/evaluation')
def evaluation(): return read('evaluation.json')

@router.get('/provenance')
def provenance(): return read('manifest.json')

@router.get('/evidence/{evidence_id}')
def evidence(evidence_id: str):
    if evidence_id not in {e['id'] for e in demo()['evidence']}: raise HTTPException(404)
    return read('evidence/' + evidence_id + '.json')

@router.get('/events/{event_id}')
def event(event_id: int):
    if event_id not in {e['id'] for e in demo()['events']}: raise HTTPException(404)
    return read('events/' + str(event_id) + '.json')

@router.get('/patch')
def patch(): return read('patch.json')

@router.get('/patch.diff', response_class=PlainTextResponse)
def patch_diff():
    return PlainTextResponse(patch()['artifact']['submitted_diff'], media_type='text/x-diff',
                            headers={'Content-Disposition': 'attachment; filename="sentinel-candidate.diff"'})

@router.get('/history/{run_id}')
def history(run_id: uuid.UUID): return read('history/' + str(run_id) + '.json')

@router.get('/report', response_class=PlainTextResponse)
def report():
    d=demo();p=patch()['artifact']
    text=f"# Project Sentinel · RECORDED RUN\n\nRun: {d['run_id']}\nRecorded at: {d['recorded_at']}\nModel: {d['model']}\n\n"
    text+=f"## Root Cause\n{d['diagnosis']['root_cause']}\n\n## Verification\n{d['critic']['verdict']}\n{d['critic']['verification_summary']}\n\n"
    text+='## Candidate · NOT DEPLOYED\n```diff\n'+p['submitted_diff']+'```\n\n'+p['candidate_test']['output']
    text+='\n\n## Provenance\n'+json.dumps(d['provenance'],indent=2)
    return PlainTextResponse(text,headers={'Content-Disposition':'attachment; filename="sentinel-recorded-report.md"'})

@router.get('/docs')
def documentation(name: str = 'README.md'):
    allowed={name:ROOT/name for name in ('README.md','FINAL_STATUS.md','CLAIMS_MATRIX.md')}
    allowed.update({f'docs/{p.name}':p for p in (ROOT/'docs').glob('*.md')})
    if name not in allowed: raise HTTPException(404, 'Document unavailable')
    if allowed[name].is_symlink() or not allowed[name].resolve().is_relative_to(ROOT.resolve()):
        raise HTTPException(404, 'Document unavailable')
    return {'name':name,'content':allowed[name].read_text(encoding='utf-8')}

@router.get('/verification')
def verification():
    return FileResponse(ROOT/'portfolio/verification.json',media_type='application/json',
                        filename='sentinel-phase5-verification.json')

def verify_artifacts():
    manifest=read('manifest.json')
    for name,meta in manifest['files'].items():
        path=(DATA/name).resolve()
        if not path.is_relative_to(DATA.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest()!=meta['sha256']:
            raise RuntimeError('Recorded artifact integrity check failed')

def create_app():
    # Always read-only, including a accidentally false environment flag.
    os.environ['PUBLIC_DEMO_MODE']='true'
    verify_artifacts()
    app=FastAPI(title='Project Sentinel · Read-only portfolio',docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=os.getenv('DEMO_ALLOWED_HOSTS','localhost,127.0.0.1,sentinel-demo,testserver').split(','))
    @app.middleware('http')
    async def read_only(request, call_next):
        if request.method not in ('GET','HEAD'):
            response=JSONResponse({'detail':'PUBLIC_DEMO_READ_ONLY: Live AI, tools and all mutations are disabled.'},status_code=403)
        # This demo needs complete files only. Reject before Starlette's affected
        # Range parser (GHSA-7f5h-v6xp-fcq8); this is a mitigation, not an upgrade.
        elif 'range' in request.headers:
            response=PlainTextResponse('Byte-range requests are not supported.',status_code=416)
        # Route security must use the ASGI path, not a URL rebuilt from Host.
        elif request.scope['path']=='/live.html': response=PlainTextResponse(config()['message'],status_code=403)
        else: response=await call_next(request)
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'"
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Cache-Control']='no-cache'
        return response
    @app.get('/health')
    def health(): return {'status':'healthy','mode':'PUBLIC_DEMO_READ_ONLY','database_connected':False,'llm_enabled':False}
    app.include_router(router)
    for name in ('incident','replay','evidence','root-cause','patch','evaluation','architecture','documentation'):
        app.add_api_route('/'+name+'.html',lambda:FileResponse(ROOT/'web/index.html'),methods=['GET'],include_in_schema=False)
    @app.get('/favicon.ico')
    def icon(): return FileResponse(ROOT/'web/favicon.svg')
    if (ROOT/'docs/screenshots').is_dir(): app.mount('/docs/screenshots',StaticFiles(directory=ROOT/'docs/screenshots'),name='screenshots')
    app.mount('/',StaticFiles(directory=ROOT/'web',html=True),name='web')
    return app
