"""Central configuration. Secrets only ever come from environment variables (never hard-coded)."""
import os
import warnings
from datetime import timedelta, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent
ROOT_DIR = BACKEND_DIR.parent

# Real environment variables always win over .env files.
load_dotenv(BACKEND_DIR / '.env')
load_dotenv(ROOT_DIR / '.env')


def env(name: str, default: str = '') -> str:
    return os.environ.get(name, default).strip()


NEBIUS_API_KEY = env('NEBIUS_API_KEY')
NEBIUS_BASE_URL = env('NEBIUS_BASE_URL', 'https://api.tokenfactory.nebius.com/v1/')
FAST_MODEL = env('FAST_MODEL')                  # e.g. Nemotron 3 Nano Omni (copy the exact ID from Token Factory)
VISION_MODEL = env('VISION_MODEL') or FAST_MODEL
REASON_MODEL = env('REASON_MODEL')              # e.g. Nemotron 3 Super (copy the exact ID from Token Factory)
FORCE_DEMO_MODE = env('FORCE_DEMO_MODE').lower() in ('1', 'true', 'yes')

DATABASE_URL = env('DATABASE_URL') or 'sqlite:///' + str(BACKEND_DIR / 'civicclosure.db')
EXPORT_TOKEN = env('EXPORT_TOKEN')              # protects /api/export and /api/hotspots (job endpoints)
# Browsers send an Origin WITHOUT a trailing slash, so a pasted 'https://site.vercel.app/' could never match. Normalise it.
CORS_ORIGINS = [o.strip().rstrip('/') for o in env('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if o.strip()]
# Optional: a regular expression for extra allowed origins, e.g. every Vercel preview deployment of one project:
#   CORS_ORIGIN_REGEX=https://civic-closure(-[a-z0-9-]+)?\.vercel\.app
CORS_ORIGIN_REGEX = env('CORS_ORIGIN_REGEX')
WORKSPACE_TTL_DAYS = int(env('WORKSPACE_TTL_DAYS', '14'))     # demo sandboxes untouched this long are deleted (0 = keep forever)

MAX_UPLOAD_BYTES = int(env('MAX_UPLOAD_BYTES', '5000000'))
RATE_LIMIT_PER_MINUTE = int(env('RATE_LIMIT_PER_MINUTE', '40'))
DAILY_TOKEN_BUDGET = int(env('DAILY_TOKEN_BUDGET', '300000'))
LLM_TIMEOUT_S = float(env('LLM_TIMEOUT_S', '60'))
LLM_MAX_RETRIES = int(env('LLM_MAX_RETRIES', '2'))
SEED_NEW_WORKSPACES = env('SEED_NEW_WORKSPACES', 'true').lower() in ('1', 'true', 'yes')

# --- hardening ---
# How many reverse-proxy hops sit in front of the app (Render, Cloud Run, nginx...). 0 = none (local use).
# With N hops the visitor's IP is the Nth value from the RIGHT of X-Forwarded-For; values further left can be forged by the visitor.
TRUST_PROXY_HOPS = int(env('TRUST_PROXY_HOPS', '0'))
DISABLE_DOCS = env('DISABLE_DOCS').lower() in ('1', 'true', 'yes')            # hides /docs, /redoc and /openapi.json
MAX_IMAGE_PIXELS = int(env('MAX_IMAGE_PIXELS', '25000000'))                   # blocks 'decompression bomb' images
CSP_MODE = env('CSP_MODE', 'report-only').lower()                             # report-only | enforce | off
CSP_EXTRA_CONNECT = env('CSP_EXTRA_CONNECT')                                  # extra API origin if the frontend is hosted separately


def is_live() -> bool:
    """Live mode needs a key and both model IDs. Anything else is clearly-labelled Demo Mode."""
    if FORCE_DEMO_MODE:
        return False
    return bool(NEBIUS_API_KEY and FAST_MODEL and REASON_MODEL)


if CORS_ORIGIN_REGEX:
    import re
    try:
        re.compile(CORS_ORIGIN_REGEX)
    except re.error as e:
        raise SystemExit('CORS_ORIGIN_REGEX is not a valid regular expression: ' + str(e)) from None

with open(BASE_DIR / 'domain' / 'campus.yaml', encoding='utf-8') as f:
    DOMAIN = yaml.safe_load(f)

DOMAIN['directory_text'] = yaml.safe_dump({
    'departments': {k: v['name'] for k, v in DOMAIN['departments'].items()},
    'issue_types': {k: v['department'] for k, v in DOMAIN['issue_types'].items()},
})

ISSUE_TYPES = list(DOMAIN['issue_types'].keys())


_FIXED_OFFSETS = {'Asia/Kolkata': timedelta(hours=5, minutes=30), 'Asia/Calcutta': timedelta(hours=5, minutes=30)}


def campus_tz():
    """The campus timezone. Windows has no system timezone database, so this needs the 'tzdata' package
    (it is in requirements.txt). If it is still missing we fall back to a fixed offset instead of crashing."""
    name = DOMAIN['timezone']
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        if name in _FIXED_OFFSETS:
            return timezone(_FIXED_OFFSETS[name])
        warnings.warn('Timezone data for ' + name + ' is missing (pip install tzdata). Falling back to UTC.')
        return timezone.utc
