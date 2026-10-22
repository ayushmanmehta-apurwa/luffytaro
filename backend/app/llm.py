"""Nebius Token Factory client (OpenAI-compatible) with validation, bounded retries and usage tracking.

Rules this module enforces:
  * the API key stays on the backend and is only read from the environment;
  * every model answer is parsed as JSON and validated with Pydantic before it is used;
  * a model can never change database state - callers decide what to do with a validated answer;
  * if the API fails, we raise LLMError and the caller routes to a human. We never silently fall
    back to fake output while pretending it came from an NVIDIA model.
"""
import base64
import json
import re
import time

from sqlalchemy import func

from . import config
from .clock import real_now
from .models import Usage


class LLMError(Exception):
    pass


_cache = {}


def get_client():
    if 'client' not in _cache:
        from openai import OpenAI
        _cache['client'] = OpenAI(base_url=config.NEBIUS_BASE_URL, api_key=config.NEBIUS_API_KEY,
                                  timeout=config.LLM_TIMEOUT_S, max_retries=0)
    return _cache['client']


def extract_json(text: str) -> dict:
    """Strip any reasoning block, then parse the first {...} object in the text."""
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S)
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end <= start:
        raise ValueError('no JSON object found in model output')
    return json.loads(text[start:end + 1])


def img_part(jpeg_bytes: bytes) -> dict:
    return {'type': 'image_url',
            'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(jpeg_bytes).decode()}}


def tokens_used_today(db) -> int:
    midnight = real_now().replace(hour=0, minute=0, second=0, microsecond=0)
    total = db.query(func.coalesce(func.sum(Usage.total_tokens), 0)).filter(Usage.ts >= midnight).scalar()
    return int(total or 0)


def chat_json(model, messages, schema, step, db=None, workspace='public', retries=None, max_tokens=1800):
    """Call a model and return (validated_object, meta). Raises LLMError on any unrecoverable problem."""
    if not config.is_live():
        raise LLMError('live AI is not configured (Demo Mode)')
    if not model:
        raise LLMError('model id for step ' + step + ' is not configured')
    if db is not None and tokens_used_today(db) >= config.DAILY_TOKEN_BUDGET:
        raise LLMError('daily token budget reached')
    retries = config.LLM_MAX_RETRIES if retries is None else retries
    last_err = 'unknown error'
    for attempt in range(retries + 1):
        t0 = time.time()
        tokens, ok = None, False
        try:
            resp = get_client().chat.completions.create(
                model=model, messages=messages, temperature=0.0, max_tokens=max_tokens)
            tokens = getattr(getattr(resp, 'usage', None), 'total_tokens', None)
            raw = resp.choices[0].message.content or ''
            obj = schema.model_validate(extract_json(raw))
            ok = True
            meta = {'source': 'live', 'model': model, 'latency_s': round(time.time() - t0, 2),
                    'tokens': tokens, 'attempts': attempt + 1}
            return obj, meta
        except Exception as e:  # network error, timeout, bad JSON, schema failure
            last_err = type(e).__name__ + ': ' + str(e)[:300]
            if 'raw' in locals():
                # give the model one corrective turn when the problem was the output format
                messages = messages + [{'role': 'assistant', 'content': raw},
                                       {'role': 'user', 'content': 'That was invalid for the required schema (' + last_err[:200]
                                        + '). Return only the corrected JSON object.'}]
                del raw
            else:
                time.sleep(min(2 ** attempt, 4))
        finally:
            if db is not None:
                db.add(Usage(ts=real_now(), workspace=workspace, step=step, model=model,
                             total_tokens=tokens, latency_s=round(time.time() - t0, 2), ok=ok))
                db.flush()
    raise LLMError('step ' + step + ' failed after ' + str(retries + 1) + ' attempts: ' + last_err)
