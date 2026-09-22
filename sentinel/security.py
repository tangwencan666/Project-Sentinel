"""Secret removal at logging, persistence, and model input boundaries."""
import json
import logging
import os
import re
from pathlib import Path

def settings():
    config={k:v for k,v in os.environ.items() if k.startswith(('LLM_','AGENT_'))}
    path=Path('/run/sentinel/provider.env')
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key,value=line.split('=',1)
                if key.strip().startswith(('LLM_','AGENT_')):
                    config[key.strip()]=value.strip().strip('\"').strip("'")
    return config

def redact(value):
    from .redaction_walk import redact_with_snapshot
    return redact_with_snapshot(value,settings().get('LLM_API_KEY',''))

class SecretFilter(logging.Filter):
    def filter(self,record):
        record.msg=redact(record.getMessage());record.args=()
        if record.exc_info:
            record.msg+=' [exception details suppressed; structured error recorded]'
            record.exc_info=None;record.exc_text=None
        return True

def install_masking():
    for handler in logging.getLogger().handlers: handler.addFilter(SecretFilter())
    for name in ('httpx','httpcore'):
        logging.getLogger(name).setLevel(logging.WARNING)

def serial(value):
    return redact(json.loads(json.dumps(value,default=str)))
