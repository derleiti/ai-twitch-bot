"""OpenAI-compatible TriForce transport; credentials never enter prompts or logs."""
import os
import logging
import time
import re
import threading
from pathlib import Path
import base64
import mimetypes
import requests

log = logging.getLogger(__name__)
TEXT_MODELS = 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free,openrouter/nvidia/nemotron-3.5-lightning:free'
VISION_MODELS = 'openrouter/nvidia/nemotron-3.5-super-vl:free,openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free'
_backoff = {}
_lock = threading.Lock()

def free_model(model):
    return model.startswith('openrouter/') and model.endswith(':free')


def headers():
    import base64
    h = {'Content-Type': 'application/json'}
    token = os.getenv('TRIFORCE_API_TOKEN')
    user, password = os.getenv('TRIFORCE_USER'), os.getenv('TRIFORCE_PASSWORD')
    if token:
        h['Authorization'] = 'Bearer ' + token
    elif user and password:
        h['Authorization'] = 'Basic ' + base64.b64encode(f'{user}:{password}'.encode()).decode()
    return h

def chat(messages, models=None, max_tokens=512, validator=None):
    base = os.getenv('TRIFORCE_BASE', 'http://172.17.0.1:9000/v1/openai').rstrip('/')
    models = models or os.getenv('TRIFORCE_TEXT_MODELS', TEXT_MODELS).split(',')
    with requests.Session() as session:
        session.trust_env = False
        for model in filter(None, (m.strip() for m in models)):
            if not free_model(model):
                log.warning('Blocked non-free model route')
                continue
            with _lock:
                if time.monotonic() < _backoff.get(model, 0):
                    continue
            try:
                r = session.post(base + '/chat/completions', headers=headers(), json={'model':model,'messages':messages,'max_tokens':max_tokens,'stream':False}, timeout=(5,60), allow_redirects=False)
                if r.status_code != 200:
                    log.warning('TriForce model %s HTTP %s', model, r.status_code)
                    if r.status_code in (402,429,500,502,503,504):
                        try:
                            delay = min(3600, max(60, int(r.headers.get('Retry-After', '90' if r.status_code >= 500 else '300'))))
                        except ValueError:
                            delay = 300
                        with _lock:
                            _backoff[model] = time.monotonic() + delay
                    continue
                choice = r.json()['choices'][0]
                content = choice['message']['content']
                if choice.get('finish_reason') not in (None, 'stop'):
                    log.warning('TriForce model %s incomplete response', model)
                    continue
                if isinstance(content, str) and content.strip():
                    result = content.strip()
                    if validator is None or validator(result):
                        log.info('TriForce model %s accepted', model)
                        return result
                log.warning('TriForce model %s invalid response', model)
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
                log.warning('TriForce model %s unavailable', model)
                with _lock:
                    _backoff[model] = time.monotonic() + 60
    return None


def vision(path, prompt):
    try:
        p = Path(path)
        if p.stat().st_size > 8 * 1024 * 1024 or time.time() - p.stat().st_mtime > float(os.getenv('VISION_MAX_FRAME_AGE_SEC','120')):
            return None
        data = p.read_bytes()
        mime = mimetypes.guess_type(p.name)[0]
        if mime not in {'image/jpeg','image/png','image/webp'} or not data:
            return None
    except OSError:
        return None
    uri = 'data:' + mime + ';base64,' + base64.b64encode(data).decode('ascii')
    return chat([{'role':'user','content':[{'type':'text','text':prompt},{'type':'image_url','image_url':{'url':uri}}]}], os.getenv('TRIFORCE_VISION_MODELS', VISION_MODELS).split(','), 1024)


def clean_comment(value, min_chars=10):
    if not isinstance(value,str):
        return None
    s = ' '.join(value.split())
    if not s or len(s) > 280 or s[0] in '/.!{' or any(x in s for x in ('```','**','http://','https://')):
        return None
    if re.search(r'(?i)hier ist|als ki|ich kann nur|system.prompt|anweisung|placeholder', s):
        return None
    if len(s) < min_chars or not re.search(r'[.!?…][”"»]?$' , s):
        return None
    if re.search(r'(?i)\b(und|oder|aber|weil|der|die|das|den|dem|mit|ohne|als|wie|ein|eine|the|and|or)\b[.!?…]+$', s):
        return None
    return s
