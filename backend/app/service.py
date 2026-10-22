"""Orchestration. main.py stays thin; every business rule lives here or in pipeline/.

AI output is validated first (Pydantic); only this code then calls the state machine."""
import hashlib
import io
from datetime import timedelta

from PIL import Image as PILImage
from PIL import ImageOps
from sqlalchemy import func

from . import config, hotspots as hotspots_mod
from .clock import get_offset_hours, real_now
from .models import Event, Hotspot, Image, Setting, Ticket, Usage
from .pipeline import duplicates, intake as intake_mod, sla, triage as triage_mod, verify
from .pipeline.audit import add_event, verify_chain
from .pipeline.statemachine import OPEN_STATES, transition


PILImage.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS     # Pillow refuses far larger images outright


class ServiceError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# ------------------------------------------------------------------ images

def validate_and_prepare(raw: bytes, max_side: int = 1024):
    """Open the file with Pillow (rejects non-images), read EXIF from the ORIGINAL, then resize to JPEG."""
    if len(raw) > config.MAX_UPLOAD_BYTES:
        raise ServiceError('Photo is too large (limit ' + str(config.MAX_UPLOAD_BYTES // 1_000_000) + ' MB).', 413)
    try:
        probe = PILImage.open(io.BytesIO(raw))
        fmt = (probe.format or '').upper()
        too_big = probe.width * probe.height > config.MAX_IMAGE_PIXELS
        if not too_big:
            probe.verify()
    except Exception:
        raise ServiceError('That file is not a readable image. Upload a JPEG, PNG or WebP photo.', 415) from None
    if too_big:
        raise ServiceError('That image has too many pixels. Use a normal phone photo.', 413)
    if fmt not in ('JPEG', 'PNG', 'WEBP'):
        raise ServiceError('Unsupported image type ' + fmt + '. Use JPEG, PNG or WebP.', 415)
    exif = verify.exif_time(raw)
    phash = verify.phash_hex(raw)
    img = ImageOps.exif_transpose(PILImage.open(io.BytesIO(raw))).convert('RGB')
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=82)
    return buf.getvalue(), exif, phash, hashlib.sha256(raw).hexdigest()


def save_image(db, ticket, kind, raw):
    jpeg, exif, phash, sha = validate_and_prepare(raw)
    row = Image(ticket_id=ticket.id, workspace=ticket.workspace, kind=kind, data=jpeg, sha256=sha,
                phash=phash, exif_time=exif, created_at=real_now())
    db.add(row)
    db.flush()
    return row


def report_image(db, ticket_id):
    return db.query(Image).filter(Image.ticket_id == ticket_id, Image.kind == 'report').order_by(Image.id).first()


# ------------------------------------------------------------------ serialization

def event_dict(e):
    return {'seq': e.seq, 'ts': e.ts, 'actor': e.actor, 'type': e.type, 'payload': e.payload, 'hash': e.hash[:12]}


def clock_ctx(db, workspace):
    """Read the demo-clock offset ONCE per request (it used to be re-read for every ticket in a list)."""
    offset = get_offset_hours(db, workspace)
    return {'offset': offset, 'now': real_now() + timedelta(hours=offset)}


def ticket_dict(db, t, detail=False, clk=None):
    clk = clk or clock_ctx(db, t.workspace)
    now = clk['now']
    dept = config.DOMAIN['departments'].get(t.department or '', {}).get('name')
    cfg = config.DOMAIN['issue_types'].get(t.issue_type or 'other', {})
    d = {
        'id': t.id, 'state': t.state, 'issue_type': t.issue_type, 'issue_label': cfg.get('label', t.issue_type),
        'department': t.department, 'department_name': dept, 'urgency': t.urgency,
        'building': t.building, 'location_text': t.location_text, 'summary': t.summary,
        'language': t.language, 'confidence': t.confidence, 'needs_human': t.needs_human,
        'report_count': t.report_count, 'ai_source': t.ai_source, 'synthetic': t.synthetic,
        'escalation_level': t.escalation_level, 'last_verdict': t.last_verdict,
        'followup_question': t.followup_question, 'safety_hazard': t.safety_hazard,
        'visual_closure_check': bool(cfg.get('closure_check')),
        'created_at': t.created_at.isoformat() if t.created_at else None,
        'due_at': t.due_at.isoformat() if t.due_at else None,
        'sla': sla.sla_status(t, now), 'demo_clock_offset_hours': clk['offset'],
    }
    if detail:
        d['original_text'] = t.original_text
        d['events'] = [event_dict(e) for e in db.query(Event).filter(Event.ticket_id == t.id).order_by(Event.seq).all()]
        d['images'] = [{'id': i.id, 'kind': i.kind, 'exif_time': i.exif_time.isoformat() if i.exif_time else None,
                        'created_at': i.created_at.isoformat() if i.created_at else None}
                       for i in db.query(Image).filter(Image.ticket_id == t.id).order_by(Image.id).all()]
    return d


def get_ticket(db, workspace, ticket_id) -> Ticket:
    t = db.query(Ticket).filter(Ticket.id == ticket_id, Ticket.workspace == workspace).first()
    if not t:
        raise ServiceError('Ticket not found in this workspace.', 404)
    return t


# ------------------------------------------------------------------ creating reports

def _building_from(building, intake_location):
    names = {n.lower(): n for n in config.DOMAIN['locations']}
    for cand in (building, intake_location):
        if cand and cand.strip().lower() in names:
            return names[cand.strip().lower()]
    for cand in (building, intake_location):
        for low, name in names.items():
            if cand and low in cand.lower():
                return name
    return None


def create_report(db, workspace, reporter_id, text, building, detail, lat, lng, raw_photo, category=None):
    text = (text or '').strip()
    if len(text) < 5:
        raise ServiceError('Describe the problem in at least a few words.', 422)
    if len(text) > 2000:
        raise ServiceError('Description is too long (limit 2000 characters).', 422)
    if building and building not in config.DOMAIN['locations']:
        raise ServiceError('Unknown campus location.', 422)
    if category and category not in config.ISSUE_TYPES:
        raise ServiceError('Unknown issue category.', 422)
    jpeg = None
    if raw_photo:
        jpeg = validate_and_prepare(raw_photo)[0]      # validates early, before any AI call

    trail = []
    intake, m1 = intake_mod.run_intake(db, workspace, text, building, detail, jpeg, category)
    trail.append({'step': 'Intake', 'decision': intake.issue_type + ' / urgency ' + intake.urgency,
                  'why': intake.summary, 'confidence': intake.confidence, **_meta_view(m1)})
    route, m2 = triage_mod.triage(db, workspace, intake)
    trail.append({'step': 'Routing', 'decision': (route.department or 'human review'),
                  'why': route.rationale, 'confidence': route.confidence, **_meta_view(m2)})

    building = _building_from(building, intake.location_text)
    location_text = ((building or '') + (', ' + detail if detail else '')).strip(', ') or intake.location_text
    ai_source = 'live' if config.is_live() else 'demo'

    cands = duplicates.candidates(db, workspace, route.issue_type, building, location_text, lat, lng, intake.summary)
    dup, m3 = duplicates.judge_duplicate(db, workspace, intake.summary, location_text, cands)
    trail.append({'step': 'Duplicate check', 'decision': ('merged into #' + str(dup.duplicate_of)) if dup.duplicate_of else 'new problem',
                  'why': dup.reason, 'confidence': dup.confidence, **_meta_view(m3)})

    if dup.duplicate_of:
        t = get_ticket(db, workspace, dup.duplicate_of)
        t.report_count += 1
        if reporter_id and reporter_id not in (t.reporter_ids or []):
            t.reporter_ids = list(t.reporter_ids or []) + [reporter_id]
        bumped = False
        if t.report_count >= 4 and t.urgency != 'high':
            t.urgency, bumped = 'high', True
            sla.set_due(t)
        t.updated_at = real_now()
        add_event(db, t.id, 'pipeline', 'CORROBORATED', {
            'new_summary': intake.summary, 'report_count': t.report_count, 'urgency_raised': bumped,
            'duplicate_judgement': dup.model_dump(), 'meta': _meta_view(m3), 'possible_prompt_injection': m1.get('possible_prompt_injection', False)})
        db.commit()
        return {'merged_into': t.id, 'ticket': ticket_dict(db, t), 'trail': trail, 'followup': None}

    now = real_now()
    t = Ticket(workspace=workspace, state='NEW', issue_type=route.issue_type, department=route.department,
               urgency=intake.urgency, building=building, location_text=location_text, lat=lat, lng=lng,
               summary=intake.summary, original_text=text, language=intake.language, safety_hazard=intake.safety_hazard,
               missing_info=intake.missing_info, confidence=route.confidence if m2.get('source') != 'rules' else intake.confidence,
               needs_human=route.needs_human, reporter_ids=[reporter_id] if reporter_id else [],
               ai_source=ai_source, synthetic=False, created_at=now, updated_at=now)
    if building:
        t.missing_info = [m for m in (t.missing_info or []) if m not in ('location',)]
    db.add(t)
    db.flush()
    add_event(db, t.id, 'reporter', 'CREATED', {'text_sha256': hashlib.sha256(text.encode()).hexdigest(), 'building': building,
                                                 'has_photo': bool(raw_photo), 'language': intake.language})
    if raw_photo:
        save_image(db, t, 'report', raw_photo)
    add_event(db, t.id, 'pipeline', 'INTAKE', {'result': intake.model_dump(), 'meta': m1})
    add_event(db, t.id, 'pipeline', 'ROUTED', {'result': route.model_dump(), 'meta': m2})
    add_event(db, t.id, 'pipeline', 'DUPLICATE_CHECK', {'result': dup.model_dump(), 'candidates': [c.id for c, _ in cands], 'meta': m3})
    if m1.get('possible_prompt_injection'):
        add_event(db, t.id, 'pipeline', 'INJECTION_FLAG', {'note': 'Report text looked like an instruction to the system. It was treated as data only.'})

    q = triage_mod.followup_question(t.missing_info)
    t.followup_question = q
    if q:
        transition(db, t, 'NEEDS_INFO', 'pipeline', 'waiting for the reporter: ' + q)
    else:
        transition(db, t, 'TRIAGED', 'pipeline', 'intake complete')
        if not t.needs_human:
            sla.set_due(t)
            transition(db, t, 'ASSIGNED', 'pipeline', 'routed to ' + str(t.department))
        else:
            add_event(db, t.id, 'pipeline', 'HUMAN_REVIEW_REQUESTED', {'reason': route.rationale})
    db.commit()
    return {'ticket_id': t.id, 'ticket': ticket_dict(db, t), 'trail': trail, 'followup': q}


def _meta_view(m):
    return {'source': m.get('source'), 'model': m.get('model'), 'latency_s': m.get('latency_s'),
            'tokens': m.get('tokens'), 'error': m.get('error')}


def answer_followup(db, workspace, ticket_id, building, detail):
    t = get_ticket(db, workspace, ticket_id)
    if t.state != 'NEEDS_INFO':
        raise ServiceError('This ticket is not waiting for more information.', 409)
    b = _building_from(building, None)
    if not b:
        raise ServiceError('Choose one of the campus locations.', 422)
    t.building = b
    t.location_text = (b + (', ' + detail if detail else '')).strip(', ')
    t.missing_info = [m for m in (t.missing_info or []) if m not in ('location', 'which_floor')]
    t.followup_question = None
    add_event(db, t.id, 'reporter', 'INFO_PROVIDED', {'building': b, 'detail': detail})
    if t.needs_human or not t.department:
        transition(db, t, 'TRIAGED', 'pipeline', 'information received; needs human routing')
        add_event(db, t.id, 'pipeline', 'HUMAN_REVIEW_REQUESTED', {'reason': 'department not decided'})
    else:
        sla.set_due(t)
        transition(db, t, 'ASSIGNED', 'pipeline', 'information received; routed to ' + t.department)
    db.commit()
    return ticket_dict(db, t, detail=True)


# ------------------------------------------------------------------ department actions

def start_work(db, workspace, ticket_id, actor):
    t = get_ticket(db, workspace, ticket_id)
    transition(db, t, 'IN_PROGRESS', actor, 'work started')
    db.commit()
    return ticket_dict(db, t, detail=True)


def claim_closure(db, workspace, ticket_id, actor, raw_after, note):
    t = get_ticket(db, workspace, ticket_id)
    if t.state not in ('ASSIGNED', 'IN_PROGRESS', 'NEEDS_EVIDENCE', 'REOPENED'):
        raise ServiceError('A closure cannot be claimed while the ticket is ' + t.state + '.', 409)
    if t.state == 'REOPENED':
        transition(db, t, 'IN_PROGRESS', actor, 'work resumed after reopening')
    transition(db, t, 'CLOSURE_CLAIMED', actor, 'department says the problem is fixed',
               {'note': (note or '')[:300], 'note_is_untrusted': True})
    cfg = config.DOMAIN['issue_types'].get(t.issue_type, {}).get('closure_check')
    if not cfg:
        # not visible in a photo: reporter confirmation or a human reviewer decides
        if raw_after:
            save_image(db, t, 'after', raw_after)
        add_event(db, t.id, 'verifier', 'AWAITING_CONFIRMATION', {
            'reason': 'This problem type cannot be checked from a photo. The reporter must confirm, or a human reviewer decides.'})
        t.last_verdict = 'awaiting_confirmation'
        db.commit()
        return {'verdict': 'awaiting_confirmation', 'checks': [], 'what_to_fix': [
            'The reporter needs to confirm the fix, or an administrator can decide.'], 'ticket': ticket_dict(db, t, detail=True)}
    if not raw_after:
        raise ServiceError('Upload an after-repair photo to claim this closure.', 422)
    jpeg, exif, phash, sha = validate_and_prepare(raw_after)
    before = report_image(db, t.id)
    checks, metas = verify.run_gate(db, t, before, raw_after, jpeg, sha)
    save_image(db, t, 'after', raw_after)           # saved after the reuse check so it does not match itself
    v = verify.apply_verdict(db, t, checks, metas)
    db.commit()
    return {'verdict': v, 'checks': checks, 'what_to_fix': verify.explain_missing(checks) if v != 'verified' else [],
            'ticket': ticket_dict(db, t, detail=True)}


def reporter_confirm(db, workspace, ticket_id, actor, fixed: bool, comment):
    t = get_ticket(db, workspace, ticket_id)
    add_event(db, t.id, 'reporter', 'REPORTER_CONFIRMATION', {'fixed': fixed, 'comment': (comment or '')[:300]})
    if t.state == 'CLOSURE_CLAIMED' and not config.DOMAIN['issue_types'][t.issue_type]['closure_check']:
        if fixed:
            transition(db, t, 'VERIFIED_CLOSED', 'verifier', 'reporter confirmed the fix (problem type has no photo check)')
            t.last_verdict = 'verified'
        else:
            transition(db, t, 'REOPENED', 'verifier', 'reporter says the problem is not fixed')
            t.last_verdict = 'contradicted'
    elif t.state == 'VERIFIED_CLOSED' and not fixed:
        transition(db, t, 'REOPENED', 'reporter', 'reporter disputes the closure')
    elif t.state in ('CLOSURE_CLAIMED', 'NEEDS_EVIDENCE') and not fixed:
        transition(db, t, 'REOPENED', 'reporter', 'reporter says the problem is not fixed')
    elif fixed:
        # A reporter's "fixed" never closes a photo-checked ticket by itself; it is recorded as extra evidence.
        add_event(db, t.id, 'pipeline', 'NOTE', {'text': 'Reporter says it is fixed. This is recorded as evidence; closure still needs the verification gate or a human reviewer.'})
    db.commit()
    return ticket_dict(db, t, detail=True)


def human_decision(db, workspace, ticket_id, decision, reason, department):
    t = get_ticket(db, workspace, ticket_id)
    if decision == 'assign_department':
        if department not in config.DOMAIN['departments']:
            raise ServiceError('Choose a valid department.', 422)
        t.department, t.needs_human = department, False
        if t.state == 'NEEDS_INFO':
            raise ServiceError('The reporter has not provided the location yet.', 409)
        sla.set_due(t)
        add_event(db, t.id, 'human_reviewer', 'HUMAN_DECISION', {'decision': decision, 'department': department, 'reason': reason})
        transition(db, t, 'ASSIGNED', 'human_reviewer', reason or 'department chosen by a human')
    elif decision == 'approve_closure':
        add_event(db, t.id, 'human_reviewer', 'HUMAN_DECISION', {'decision': decision, 'reason': reason})
        t.last_verdict = 'verified'
        transition(db, t, 'VERIFIED_CLOSED', 'human_reviewer', reason or 'approved by a human reviewer')
    elif decision == 'reject_closure':
        add_event(db, t.id, 'human_reviewer', 'HUMAN_DECISION', {'decision': decision, 'reason': reason})
        t.last_verdict = 'contradicted'
        transition(db, t, 'REOPENED', 'human_reviewer', reason or 'closure rejected by a human reviewer')
    else:
        raise ServiceError('Unknown decision.', 422)
    db.commit()
    return ticket_dict(db, t, detail=True)


def delete_my_data(db, workspace, ticket_id):
    """Privacy control: remove photos, free text and event payloads. The hash chain still verifies."""
    t = get_ticket(db, workspace, ticket_id)
    db.query(Image).filter(Image.ticket_id == t.id).delete()
    for e in db.query(Event).filter(Event.ticket_id == t.id).all():
        e.payload = None
    t.original_text, t.summary, t.lat, t.lng = None, '[deleted at the reporter\'s request]', None, None
    db.flush()
    ok, msg, n = verify_chain(db, t.id)
    db.commit()
    return {'deleted': True, 'chain_still_valid': ok, 'message': msg}


# ------------------------------------------------------------------ dashboards

def list_tickets(db, workspace, state=None, department=None, urgency=None, reporter_id=None, needs_human=None):
    q = db.query(Ticket).filter(Ticket.workspace == workspace)
    if state:
        q = q.filter(Ticket.state == state)
    if department:
        q = q.filter(Ticket.department == department)
    if urgency:
        q = q.filter(Ticket.urgency == urgency)
    if needs_human is not None:
        q = q.filter(Ticket.needs_human.is_(needs_human))
    rows = q.order_by(Ticket.id.desc()).all()
    if reporter_id:
        rows = [t for t in rows if reporter_id in (t.reporter_ids or [])]
    clk = clock_ctx(db, workspace)
    return [ticket_dict(db, t, clk=clk) for t in rows]


def stats(db, workspace):
    tickets = db.query(Ticket).filter(Ticket.workspace == workspace).all()
    clk = clock_ctx(db, workspace)
    now = clk['now']
    by_state = {}
    for t in tickets:
        by_state[t.state] = by_state.get(t.state, 0) + 1
    open_ = [t for t in tickets if t.state in OPEN_STATES]
    dept_rows = []
    for key, d in config.DOMAIN['departments'].items():
        mine = [t for t in tickets if t.department == key]
        closed = [t for t in mine if t.state == 'VERIFIED_CLOSED']
        overdue = [t for t in mine if t.state in OPEN_STATES and t.due_at and t.due_at < now]
        dept_rows.append({'key': key, 'name': d['name'], 'total': len(mine), 'open': len([t for t in mine if t.state in OPEN_STATES]),
                          'verified_closed': len(closed), 'overdue': len(overdue),
                          'reopened': len([t for t in mine if t.state == 'REOPENED'])})
    esc = db.query(Event).join(Ticket, Ticket.id == Event.ticket_id).filter(Ticket.workspace == workspace, Event.type == 'ESCALATED').all()
    human_triage = [t for t in open_ if t.needs_human and t.state == 'TRIAGED']
    human_closure = [t for t in open_ if t.state == 'CLOSURE_CLAIMED' and not config.DOMAIN['issue_types'][t.issue_type]['closure_check']] + \
                    [t for t in open_ if t.state == 'NEEDS_EVIDENCE']
    midnight = real_now().replace(hour=0, minute=0, second=0, microsecond=0)
    tokens_today = db.query(func.coalesce(func.sum(Usage.total_tokens), 0)).filter(Usage.ts >= midnight).scalar() or 0
    ai_calls = db.query(func.count(Usage.id)).filter(Usage.workspace == workspace).scalar() or 0
    return {
        'total': len(tickets), 'pending': len(open_), 'verified_closed': by_state.get('VERIFIED_CLOSED', 0),
        'reopened': by_state.get('REOPENED', 0), 'needs_evidence': by_state.get('NEEDS_EVIDENCE', 0),
        'by_state': by_state, 'departments': dept_rows,
        'escalations_real': len([e for e in esc if not (e.payload or {}).get('simulated') and not (e.payload or {}).get('sample_data')]),
        'escalations_simulated': len([e for e in esc if (e.payload or {}).get('simulated') or (e.payload or {}).get('sample_data')]),
        'overdue_now': len([t for t in open_ if t.due_at and t.due_at < now]),
        'human_queue': {'routing': [ticket_dict(db, t, clk=clk) for t in human_triage], 'closure': [ticket_dict(db, t, clk=clk) for t in human_closure]},
        'demo_clock_offset_hours': clk['offset'],
        'ai': {'mode': 'live' if config.is_live() else 'demo', 'calls_in_workspace': ai_calls, 'tokens_today_all_workspaces': int(tokens_today),
               'daily_token_budget': config.DAILY_TOKEN_BUDGET},
        'sample_data_included': any(t.synthetic for t in tickets),
    }


def audit(db, workspace, ticket_id):
    t = get_ticket(db, workspace, ticket_id)
    ok, msg, n = verify_chain(db, t.id)
    events = db.query(Event).filter(Event.ticket_id == t.id).order_by(Event.seq).all()
    return {'ticket_id': t.id, 'chain_ok': ok, 'message': msg, 'event_count': n,
            'note': 'Tamper-evident, not tamper-proof: someone with full database control could rebuild the chain.',
            'events': [event_dict(e) | {'prev_hash': e.prev_hash[:12]} for e in events]}


# ------------------------------------------------------------------ hotspots

def run_hotspots_inline(db, workspace):
    tickets = [t for t in db.query(Ticket).filter(Ticket.workspace == workspace, Ticket.state.in_(OPEN_STATES)).all()]
    rows = [{'id': t.id, 'issue_type': t.issue_type, 'building': t.building, 'location_text': t.location_text,
             'summary': t.summary, 'urgency': t.urgency} for t in tickets]
    found, source = hotspots_mod.analyze(db, workspace, rows)
    db.add(Hotspot(workspace=workspace, created_at=real_now(), source=source, data=found))
    db.commit()
    return {'source': source, 'hotspots': found}


def latest_hotspots(db, workspace):
    h = db.query(Hotspot).filter(Hotspot.workspace == workspace).order_by(Hotspot.id.desc()).first()
    if not h:
        return {'source': None, 'created_at': None, 'hotspots': []}
    return {'source': h.source, 'created_at': h.created_at.isoformat(), 'hotspots': h.data}


def export_open_tickets(db, workspace):
    since = real_now() - timedelta(days=14)
    rows = db.query(Ticket).filter(Ticket.workspace == workspace, Ticket.state.in_(OPEN_STATES), Ticket.created_at >= since).all()
    return [{'id': t.id, 'issue_type': t.issue_type, 'building': t.building, 'location_text': t.location_text,
             'summary': t.summary, 'urgency': t.urgency, 'created_at': t.created_at.isoformat()} for t in rows]


def reset_workspace(db, workspace):
    ids = [t.id for t in db.query(Ticket.id).filter(Ticket.workspace == workspace).all()]
    if ids:
        db.query(Event).filter(Event.ticket_id.in_(ids)).delete(synchronize_session=False)
        db.query(Image).filter(Image.ticket_id.in_(ids)).delete(synchronize_session=False)
    db.query(Ticket).filter(Ticket.workspace == workspace).delete(synchronize_session=False)
    db.query(Hotspot).filter(Hotspot.workspace == workspace).delete(synchronize_session=False)
    db.query(Setting).filter(Setting.key.in_(['seeded:' + workspace, 'clock_offset_hours:' + workspace])).delete(synchronize_session=False)
    db.commit()


def purge_old_workspaces(db, ttl_days: int) -> int:
    """Delete demo sandboxes (tickets, photos, events, usage) that were created and last touched more than ttl_days ago."""
    from datetime import datetime
    if ttl_days <= 0:
        return 0
    cutoff = real_now() - timedelta(days=ttl_days)
    purged = 0
    for row in db.query(Setting).filter(Setting.key.like('seeded:%')).all():
        ws = row.key.split(':', 1)[1]
        try:
            created = datetime.fromisoformat(row.value)
        except ValueError:                      # legacy marker without a date: leave it alone
            continue
        if created >= cutoff:
            continue
        last = db.query(func.max(Ticket.updated_at)).filter(Ticket.workspace == ws).scalar()
        if last is not None and last >= cutoff:
            continue
        db.query(Usage).filter(Usage.workspace == ws).delete(synchronize_session=False)
        reset_workspace(db, ws)                 # also removes the 'seeded' marker and the demo-clock setting
        purged += 1
    db.query(Usage).filter(Usage.ts < cutoff).delete(synchronize_session=False)
    db.commit()
    return purged
