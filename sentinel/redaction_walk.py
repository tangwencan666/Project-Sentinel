"""Recursive secret masking using one request-local key snapshot."""
import re

def redact_with_snapshot(value,key):
    if isinstance(value,dict):
        return {k:'[REDACTED]' if any(s in str(k).lower() for s in ('api_key','authorization','password','secret'))
                else redact_with_snapshot(v,key) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [redact_with_snapshot(v,key) for v in value]
    if not isinstance(value,str): return value
    if key: value=value.replace(key,'[REDACTED]')
    value=re.sub(r'(?i)(bearer\s+)[^\s"\'}]+',r'\1[REDACTED]',value)
    value=re.sub(r'(?i)((?:api[_-]?key|password|secret)\s*[=:]\s*)[^\s,;"\'}]+',r'\1[REDACTED]',value)
    return re.sub(r'(?i)(https?://)[^/@\s]+:[^/@\s]+@',r'\1[REDACTED]@',value)

def redact(value,settings):
    return redact_with_snapshot(value,settings().get('LLM_API_KEY',''))
