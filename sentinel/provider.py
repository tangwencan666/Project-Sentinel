"""OpenAI-compatible transport. No provider response bodies or headers in error logs."""
import asyncio
import hashlib
import json
import time
import uuid
from urllib.parse import urlsplit
import httpx
from psycopg.types.json import Jsonb
from services.runtime import query
from .security import settings,serial,redact

STATE={'status':'not_checked','last_error':None,'last_success_at':None}

class ProviderError(RuntimeError):
    def __init__(self,code,retryable=False,status=None):
        self.code=code;self.retryable=retryable;self.status=status
        super().__init__(code)
    def public(self): return {'code':self.code,'retryable':self.retryable,'http_status':self.status}

def configuration():
    cfg=settings()
    if not cfg.get('LLM_API_KEY') or not cfg.get('LLM_MODEL'): raise ProviderError('PROVIDER_NOT_CONFIGURED')
    url=cfg.get('LLM_BASE_URL','').rstrip('/')
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment: raise ProviderError('INVALID_PROVIDER_URL')
    return cfg

def status():
    cfg=settings()
    configured=bool(cfg.get('LLM_API_KEY') and cfg.get('LLM_MODEL'))
    return {'configured':configured,'model':redact(cfg.get('LLM_MODEL') or None),'status':STATE['status'] if configured else 'not_configured','last_error':STATE['last_error'],'last_success_at':STATE['last_success_at'],'mode':'AI','silent_fallback':False}

def usage_values(payload,cfg):
    usage=payload.get('usage') or {}
    def count(key):
        value=usage.get(key)
        return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None
    inp,out,total=count('prompt_tokens'),count('completion_tokens'),count('total_tokens')
    cost=None;prices=None
    if inp is not None and out is not None and cfg.get('LLM_INPUT_PRICE_PER_MILLION') and cfg.get('LLM_OUTPUT_PRICE_PER_MILLION'):
        a,b=float(cfg['LLM_INPUT_PRICE_PER_MILLION']),float(cfg['LLM_OUTPUT_PRICE_PER_MILLION'])
        if a>=0 and b>=0:
            cost=(inp*a+out*b)/1_000_000;prices={'input_per_million':a,'output_per_million':b,'currency':'USD','source':'operator_configured'}
    return inp,out,total,cost,prices

async def request_once(client,cfg,messages,tools=None,tool_choice=None):
    body={'model':cfg['LLM_MODEL'],'messages':messages,'max_tokens':int(cfg.get('LLM_MAX_OUTPUT_TOKENS',2500))}
    if tools: body.update(tools=tools,tool_choice=tool_choice or 'auto')
    elif any(m.get('role')=='system' and 'JSON' in m.get('content','') for m in messages): body['response_format']={'type':'json_object'}
    try:
        response=await client.post(cfg['LLM_BASE_URL'].rstrip('/')+'/chat/completions',headers={'Authorization':'Bearer '+cfg['LLM_API_KEY']},json=body,timeout=float(cfg.get('LLM_TIMEOUT_SECONDS',45)))
    except httpx.TimeoutException as exc: raise ProviderError('LLM_TIMEOUT',True) from None
    except httpx.HTTPError: raise ProviderError('PROVIDER_NETWORK_ERROR',True) from None
    if response.status_code!=200:
        raise ProviderError('PROVIDER_HTTP_ERROR',response.status_code in (429,500,502,503,504),response.status_code)
    try:
        payload=response.json();message=payload['choices'][0]['message']
        if not isinstance(message,dict) or message.get('role')!='assistant': raise ValueError()
    except (ValueError,KeyError,IndexError,TypeError): raise ProviderError('INVALID_PROVIDER_JSON') from None
    return message,payload

async def complete(incident_id,run_id,agent,messages,tools=None,tool_choice=None,*,include_metadata=False,retry_hook=None,logical_request_id=None):
    request_digest=hashlib.sha256(json.dumps(serial({'messages':messages,'tools':tools,'tool_choice':tool_choice}),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    if logical_request_id and run_id:
        previous=await query("SELECT id,request_digest,response_payload,diagnostics FROM llm_calls WHERE run_id=%s AND logical_request_id=%s AND status='succeeded' AND response_payload IS NOT NULL ORDER BY started_at LIMIT 1",(run_id,logical_request_id),one=True)
        if previous:
            if previous['request_digest']!=request_digest: raise ProviderError('REQUEST_REPLAY_MISMATCH')
            result=dict(previous['response_payload'])
            if include_metadata: result['_runtime']={'call_id':str(previous['id']),**previous['diagnostics'],'response_replayed':True}
            return result
    cfg=configuration()
    if run_id:
        budget=await query('SELECT coalesce(sum(total_tokens),0) n FROM llm_calls WHERE run_id=%s',(run_id,),one=True)
        if budget['n']>=int(cfg.get('AGENT_MAX_TOTAL_TOKENS',300000)): raise ProviderError('TOKEN_BUDGET_EXCEEDED')
    # Hard character ceiling is a context safeguard, never reported as token usage.
    if len(json.dumps(messages,ensure_ascii=False))>int(cfg.get('AGENT_MAX_CONTEXT_CHARS',90000)): raise ProviderError('CONTEXT_BUDGET_EXCEEDED')
    async with httpx.AsyncClient() as client:
        for attempt in range(3):
            if attempt and retry_hook: await retry_hook()
            call_id=str(uuid.uuid4())
            started=time.monotonic()
            estimated=(len(json.dumps({'messages':messages,'tools':tools},ensure_ascii=False))+3)//4
            await query('INSERT INTO llm_calls(id,incident_id,run_id,agent,model,status,request_estimated_tokens,logical_request_id,request_digest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(call_id,incident_id,run_id,agent,cfg['LLM_MODEL'],'started',estimated,logical_request_id,request_digest))
            try:
                message,payload=await request_once(client,cfg,messages,tools,tool_choice)
                inp,out,total,cost,prices=usage_values(payload,cfg)
                finish=payload['choices'][0].get('finish_reason')
                diagnostics=serial({'provider':urlsplit(cfg['LLM_BASE_URL']).hostname,'model':cfg['LLM_MODEL'],
                    'request_id':payload.get('id'),'finish_reason':finish,'input_tokens':inp,'output_tokens':out,
                    'total_tokens':total,'latency_seconds':time.monotonic()-started,
                    'raw_output_length':len(json.dumps(message,ensure_ascii=False)),
                    'parse_status':'pending','parse_error':None,'schema_error':None,
                    'truncation':'OUTPUT_TRUNCATED_CONFIRMED' if finish=='length' else
                        'OUTPUT_TRUNCATED_SUSPECTED' if out is not None and out>=int(cfg.get('LLM_MAX_OUTPUT_TOKENS',2500)) else None})
                public=serial({k:v for k,v in message.items() if k in ('role','content','tool_calls')})
                # Response, billing and metadata commit together before the caller checkpoint.
                # Never persist provider-specific hidden reasoning fields.
                await query("UPDATE llm_calls SET finished_at=now(),status='succeeded',input_tokens=%s,output_tokens=%s,total_tokens=%s,estimated_cost=%s,pricing=%s,diagnostics=%s,response_payload=%s WHERE id=%s",
                    (inp,out,total,cost,Jsonb(prices),Jsonb(diagnostics),Jsonb(public),call_id))
                STATE.update(status='available',last_error=None,last_success_at=time.time())
                # Ignore reasoning_content and all other provider-specific hidden reasoning fields.
                result=dict(public)
                if include_metadata: result['_runtime']={'call_id':call_id,**diagnostics}
                return result
            except ProviderError as exc:
                await query("UPDATE llm_calls SET finished_at=now(),status='failed',error=%s WHERE id=%s",(Jsonb(exc.public()),call_id))
                await query('UPDATE llm_calls SET diagnostics=%s WHERE id=%s',(Jsonb({'provider':urlsplit(cfg['LLM_BASE_URL']).hostname,
                    'model':cfg['LLM_MODEL'],'latency_seconds':time.monotonic()-started,'request_id':None,
                    'finish_reason':None,'raw_output_length':None,'parse_status':'transport_failed',
                    'parse_error':exc.code if exc.code=='INVALID_PROVIDER_JSON' else None,'schema_error':None}),call_id))
                STATE.update(status='unavailable',last_error=exc.public())
                if not exc.retryable or attempt==2: raise
                await asyncio.sleep(min(2**attempt,4))
