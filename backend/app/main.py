"""CivicClosure API. Roles and workspaces come from request headers:
  X-Workspace  private demo workspace id (each visitor gets their own sandbox)
  X-Role       reporter | department | admin   (DEMO ROLE SWITCHER - this is NOT real authentication)
  X-Reporter   anonymous id of the browser, used for 'my reports'
"""
import asyncio
import hmac
import json
import re
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Literal, Optional

from sqlalchemy import text
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from . import config, samples, service
from .clock import get_offset_hours, set_offset_hours
from .db import SessionLocal, get_db, init_db
from .models import Hotspot, Image
from .pipeline.sla import sla_tick
from .pipeline.statemachine import ClosureNotAllowed, TransitionError
from .seed import seed_workspace
from .service import ServiceError

WS_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
ROLES = ('reporter', 'department', 'admin')


# ------------------------------------------------------------------ app + lifecycle

async def _sla_loop():
    rounds = 0
    while True:
        await asyncio.sleep(60)
        rounds += 1
        try:
            with SessionLocal() as db:
                for (ws,) in db.query(service.Ticket.workspace).distinct().all():
                    sla_tick(db, ws)
                db.commit()
                if rounds % 60 == 0:                    # about once an hour
                    n = service.purge_old_workspaces(db, config.WORKSPACE_TTL_DAYS)
                    if n:
                        print('purged', n, 'old demo workspace(s)')
        except Exception as e:  # never let the background loop die
            print('background loop error:', type(e).__name__, e)


@asynccontextmanager
async def lifespan(app):
    init_db()
    # One safe line in the host's logs: handy when a deploy 'does not work'. Never prints secrets.
    print('CivicClosure starting | mode=' + ('live' if config.is_live() else 'demo') + ' | database=' + config.DATABASE_URL.split(':')[0] +
          ' | cors_origins=' + str(config.CORS_ORIGINS) + (' | cors_regex=set' if config.CORS_ORIGIN_REGEX else '') +
          ' | trust_proxy_hops=' + str(config.TRUST_PROXY_HOPS) + ' | docs=' + ('off' if config.DISABLE_DOCS else 'on'), flush=True)
    task = asyncio.create_task(_sla_loop())
    yield
    task.cancel()


def _docs_kwargs():
    if config.DISABLE_DOCS:
        return {'docs_url': None, 'redoc_url': None, 'openapi_url': None}
    return {}


app = FastAPI(title='CivicClosure API', version='1.0.0', lifespan=lifespan, **_docs_kwargs())
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_origin_regex=config.CORS_ORIGIN_REGEX or None, allow_credentials=False,
                   allow_methods=['GET', 'POST', 'DELETE', 'OPTIONS'],
                   allow_headers=['Content-Type', 'X-Workspace', 'X-Role', 'X-Reporter', 'X-Token'])


def _csp():
    connect = "'self'" + (' ' + config.CSP_EXTRA_CONNECT if config.CSP_EXTRA_CONNECT else '')
    return ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
            "font-src 'self' data:; connect-src " + connect + "; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


@app.middleware('http')
async def security_headers(request: Request, call_next):
    """Standard browser protections. CSP defaults to report-only so a blind rollout cannot break the site;
    watch the browser console, then set CSP_MODE=enforce."""
    response = await call_next(request)
    h = response.headers
    h.setdefault('X-Content-Type-Options', 'nosniff')
    h.setdefault('X-Frame-Options', 'DENY')
    h.setdefault('Referrer-Policy', 'no-referrer')
    h.setdefault('Permissions-Policy', 'camera=(self), geolocation=(self), microphone=()')
    h.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
    if request.headers.get('x-forwarded-proto', request.url.scheme) == 'https':
        h.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    path = request.url.path
    if path.startswith('/api/') and not path.startswith(('/api/images/', '/api/samples/')):
        h.setdefault('Cache-Control', 'no-store')
    if config.CSP_MODE in ('report-only', 'enforce') and not path.startswith(('/docs', '/redoc')):
        h.setdefault('Content-Security-Policy' if config.CSP_MODE == 'enforce' else 'Content-Security-Policy-Report-Only', _csp())
    return response


@app.exception_handler(ServiceError)
async def _service_error(request, exc: ServiceError):
    return JSONResponse(status_code=exc.status, content={'detail': str(exc)})


@app.exception_handler(TransitionError)
async def _transition_error(request, exc):
    return JSONResponse(status_code=409, content={'detail': str(exc)})


@app.exception_handler(ClosureNotAllowed)
async def _closure_error(request, exc):
    return JSONResponse(status_code=403, content={'detail': str(exc)})


# ------------------------------------------------------------------ request context

_hits = defaultdict(deque)


def client_ip(request: Request) -> str:
    """The visitor's IP. Behind a proxy request.client.host is the PROXY, so every visitor would share one rate-limit bucket."""
    hops = config.TRUST_PROXY_HOPS
    if hops > 0:
        parts = [p.strip() for p in request.headers.get('x-forwarded-for', '').split(',') if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else 'unknown'


def rate_limit(request: Request):
    """Small in-memory per-IP limiter for write endpoints (use a shared store if you run several workers)."""
    ip = client_ip(request)
    now = time.time()
    if len(_hits) > 5000:                                   # drop stale entries so memory cannot grow without bound
        for k in [k for k, q in _hits.items() if not q or now - q[-1] > 60]:
            _hits.pop(k, None)
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(429, 'Too many requests. Please wait a minute and try again.')
    q.append(now)


class Ctx:
    def __init__(self, workspace, role, reporter, db):
        self.workspace, self.role, self.reporter, self.db = workspace, role, reporter, db

    def need(self, *roles):
        if self.role not in roles:
            raise HTTPException(403, 'This action needs the ' + ' or '.join(roles) + ' role (demo role switcher, not real authentication).')


def ctx(x_workspace: str = Header('public'), x_role: str = Header('reporter'), x_reporter: str = Header(''),
        db=Depends(get_db)) -> Ctx:
    if not WS_RE.match(x_workspace):
        raise HTTPException(400, 'Invalid workspace id.')
    if x_role not in ROLES:
        raise HTTPException(400, 'Invalid role.')
    if config.SEED_NEW_WORKSPACES and x_workspace != 'eval':
        seed_workspace(db, x_workspace)
    return Ctx(x_workspace, x_role, x_reporter[:64], db)


def job_auth(x_token: str = Header('')):
    if not config.EXPORT_TOKEN:
        raise HTTPException(503, 'Job endpoints are disabled. Set EXPORT_TOKEN in the environment to enable them.')
    if not hmac.compare_digest(x_token, config.EXPORT_TOKEN):
        raise HTTPException(401, 'Invalid or missing X-Token.')


# ------------------------------------------------------------------ bodies

class InfoBody(BaseModel):
    building: str = Field(min_length=1, max_length=80)
    detail: str = Field(default='', max_length=200)


class ConfirmBody(BaseModel):
    fixed: bool
    comment: str = Field(default='', max_length=300)


class HumanBody(BaseModel):
    decision: Literal['assign_department', 'approve_closure', 'reject_closure']
    reason: str = Field(default='', max_length=300)
    department: Optional[str] = None


class HotspotBody(BaseModel):
    hotspots: list[dict]


# ------------------------------------------------------------------ public

@app.get('/health')
def health(db=Depends(get_db)):
    mode = 'live' if config.is_live() else 'demo'
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        return JSONResponse(status_code=503, content={'status': 'degraded', 'mode': mode, 'database': 'error'})
    return {'status': 'ok', 'mode': mode, 'database': 'ok'}


@app.get('/api/config')
def get_config():
    live = config.is_live()
    return {
        'mode': 'live' if live else 'demo',
        'mode_notice': ('Live mode: decisions come from NVIDIA Nemotron models through Nebius Token Factory.' if live else
                        'DEMO MODE: no Nebius key or model IDs are configured. Results come from simple deterministic rules and image statistics, '
                        'not from NVIDIA models.'),
        'models': {'fast': config.FAST_MODEL, 'vision': config.VISION_MODEL, 'reasoning': config.REASON_MODEL} if live else None,
        'campus_name': config.DOMAIN['campus_name'],
        'departments': {k: v['name'] for k, v in config.DOMAIN['departments'].items()},
        'issue_types': {k: {'label': v['label'], 'department': v['department'], 'visual_check': bool(v['closure_check'])}
                        for k, v in config.DOMAIN['issue_types'].items()},
        'locations': config.DOMAIN['locations'],
        'thresholds': config.DOMAIN['thresholds'],
        'auth_notice': 'The role switcher is a demo convenience. It is not real authentication.',
        'evidence_notice': 'Photo timestamps and visual analysis are evidence checks, not guaranteed proof against manipulation.',
    }


@app.get('/api/samples')
def list_samples():
    return {'samples': samples.sample_catalog(),
            'note': 'Synthetic illustrations generated with Pillow. Replace them with real staged photos for a real submission.'}


@app.get('/api/samples/{name}')
def get_sample(name: str, seed: int = Query(1, ge=0, le=100000)):
    try:
        data = samples.sample_image(name, seed)
    except KeyError:
        raise HTTPException(404, 'Unknown sample.') from None
    return Response(content=data, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})


@app.get('/api/images/{image_id}')
def get_image(image_id: int, ws: str = Query('public'), db=Depends(get_db)):
    if not WS_RE.match(ws):
        raise HTTPException(400, 'Invalid workspace id.')
    img = db.query(Image).filter(Image.id == image_id, Image.workspace == ws).first()
    if not img:
        raise HTTPException(404, 'Image not found.')
    return Response(content=img.data, media_type='image/jpeg', headers={'Cache-Control': 'private, max-age=300'})


@app.get('/api/metrics')
def get_metrics():
    path = config.ROOT_DIR / 'eval' / 'results' / 'metrics.json'
    if not path.exists():
        return {'available': False, 'message': 'No evaluation has been run yet. Run: python eval/run_eval.py'}
    return {'available': True, **json.loads(path.read_text(encoding='utf-8'))}


# ------------------------------------------------------------------ reporter

@app.post('/api/reports', dependencies=[Depends(rate_limit)])
async def create_report(c: Ctx = Depends(ctx), text: str = Form(...), building: str = Form(''), detail: str = Form(''),
                        lat: Optional[float] = Form(None), lng: Optional[float] = Form(None), category: str = Form(''),
                        photo: UploadFile = File(None)):
    raw = None
    if photo is not None and photo.filename:
        raw = await photo.read(config.MAX_UPLOAD_BYTES + 1)
    if lat is not None and not (-90 <= lat <= 90) or lng is not None and not (-180 <= lng <= 180):
        raise HTTPException(422, 'GPS coordinates are out of range.')
    return service.create_report(c.db, c.workspace, c.reporter, text, building or None, detail.strip()[:200] or None, lat, lng, raw, category or None)


@app.post('/api/tickets/{ticket_id}/info', dependencies=[Depends(rate_limit)])
def provide_info(ticket_id: int, body: InfoBody, c: Ctx = Depends(ctx)):
    c.need('reporter', 'admin')
    return service.answer_followup(c.db, c.workspace, ticket_id, body.building, body.detail)


@app.post('/api/tickets/{ticket_id}/confirm', dependencies=[Depends(rate_limit)])
def confirm(ticket_id: int, body: ConfirmBody, c: Ctx = Depends(ctx)):
    c.need('reporter', 'admin')
    return service.reporter_confirm(c.db, c.workspace, ticket_id, c.role, body.fixed, body.comment)


@app.delete('/api/tickets/{ticket_id}/my_data', dependencies=[Depends(rate_limit)])
def delete_data(ticket_id: int, c: Ctx = Depends(ctx)):
    c.need('reporter', 'admin')
    return service.delete_my_data(c.db, c.workspace, ticket_id)


# ------------------------------------------------------------------ shared reads

@app.get('/api/tickets')
def list_tickets(c: Ctx = Depends(ctx), state: Optional[str] = None, department: Optional[str] = None,
                 urgency: Optional[str] = None, mine: bool = False, needs_human: Optional[bool] = None):
    return {'tickets': service.list_tickets(c.db, c.workspace, state, department, urgency,
                                            c.reporter if mine else None, needs_human)}


@app.get('/api/tickets/{ticket_id}')
def get_ticket(ticket_id: int, c: Ctx = Depends(ctx)):
    return service.ticket_dict(c.db, service.get_ticket(c.db, c.workspace, ticket_id), detail=True)


@app.get('/api/tickets/{ticket_id}/audit')
def get_audit(ticket_id: int, c: Ctx = Depends(ctx)):
    return service.audit(c.db, c.workspace, ticket_id)


# ------------------------------------------------------------------ department

@app.post('/api/tickets/{ticket_id}/start', dependencies=[Depends(rate_limit)])
def start(ticket_id: int, c: Ctx = Depends(ctx)):
    c.need('department', 'admin')
    return service.start_work(c.db, c.workspace, ticket_id, 'department')


@app.post('/api/tickets/{ticket_id}/claim_closure', dependencies=[Depends(rate_limit)])
async def claim_closure(ticket_id: int, c: Ctx = Depends(ctx), note: str = Form(''), photo: UploadFile = File(None)):
    c.need('department', 'admin')
    raw = None
    if photo is not None and photo.filename:
        raw = await photo.read(config.MAX_UPLOAD_BYTES + 1)
    return service.claim_closure(c.db, c.workspace, ticket_id, 'department', raw, note)


# ------------------------------------------------------------------ admin

@app.get('/api/stats')
def get_stats(c: Ctx = Depends(ctx)):
    c.need('admin')
    return service.stats(c.db, c.workspace)


@app.post('/api/tickets/{ticket_id}/human_decision', dependencies=[Depends(rate_limit)])
def human_decision(ticket_id: int, body: HumanBody, c: Ctx = Depends(ctx)):
    c.need('admin')
    return service.human_decision(c.db, c.workspace, ticket_id, body.decision, body.reason, body.department)


@app.post('/api/admin/advance_clock', dependencies=[Depends(rate_limit)])
def advance_clock(hours: float = Query(..., gt=0, le=720), c: Ctx = Depends(ctx)):
    """DEMO CLOCK. Moves only the moment SLA deadlines are evaluated; real timestamps are untouched."""
    c.need('admin')
    set_offset_hours(c.db, c.workspace, get_offset_hours(c.db, c.workspace) + hours)
    n = sla_tick(c.db, c.workspace)
    c.db.commit()
    return {'demo_clock_offset_hours': get_offset_hours(c.db, c.workspace), 'escalations_made': n,
            'warning': 'Demo clock is active. Escalations it causes are flagged simulated and excluded from real performance figures.'}


@app.post('/api/admin/reset_clock', dependencies=[Depends(rate_limit)])
def reset_clock(c: Ctx = Depends(ctx)):
    c.need('admin')
    set_offset_hours(c.db, c.workspace, 0.0)
    c.db.commit()
    return {'demo_clock_offset_hours': 0.0}


@app.post('/api/admin/reset_workspace', dependencies=[Depends(rate_limit)])
def reset_workspace(c: Ctx = Depends(ctx)):
    c.need('admin')
    service.reset_workspace(c.db, c.workspace)
    seed_workspace(c.db, c.workspace)
    return {'reset': True}


@app.post('/api/admin/hotspots/run', dependencies=[Depends(rate_limit)])
def run_hotspots(c: Ctx = Depends(ctx)):
    c.need('admin')
    return service.run_hotspots_inline(c.db, c.workspace)


@app.get('/api/hotspots')
def get_hotspots(c: Ctx = Depends(ctx)):
    return service.latest_hotspots(c.db, c.workspace)


# ------------------------------------------------------------------ job endpoints (token protected)

def _job_ws(workspace: str):
    if not WS_RE.match(workspace):
        raise HTTPException(400, 'Invalid workspace id.')
    return workspace


@app.get('/api/export', dependencies=[Depends(job_auth)])
def export(workspace: str = Query('demo'), db=Depends(get_db)):
    ws = _job_ws(workspace)
    if config.SEED_NEW_WORKSPACES:
        seed_workspace(db, ws)
    return {'workspace': ws, 'tickets': service.export_open_tickets(db, ws)}


@app.post('/api/hotspots', dependencies=[Depends(job_auth)])
def post_hotspots(body: HotspotBody, workspace: str = Query('demo'), db=Depends(get_db)):
    ws = _job_ws(workspace)
    from .clock import real_now
    db.add(Hotspot(workspace=ws, created_at=real_now(), source='job', data=body.hotspots))
    db.commit()
    return {'stored': len(body.hotspots)}


# ------------------------------------------------------------------ serve the built frontend (optional, for one-process deploys)

_DIST = config.ROOT_DIR / 'frontend' / 'dist'
if _DIST.exists():
    @app.get('/{path:path}', include_in_schema=False)
    def spa(path: str):
        target = (_DIST / path).resolve()
        if path and target.is_file() and _DIST.resolve() in target.parents:
            return FileResponse(target)
        return FileResponse(_DIST / 'index.html')
