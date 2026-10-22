"""Synthetic sample data so a new workspace is not empty. Every seeded ticket is flagged synthetic=True and
labelled 'Sample data' in the UI. Seeding NEVER calls an AI model and uses only generated illustrations."""
import threading
from collections import defaultdict
from datetime import timedelta

from sqlalchemy.exc import IntegrityError

from . import config
from .clock import real_now
from .models import Image, Setting, Ticket
from .pipeline.audit import add_event
from .pipeline.statemachine import transition
from .pipeline.sla import set_due
from .pipeline import verify
from .samples import scene_jpeg

SEEDS = [
    # (issue_type, building, detail, summary, urgency, end_state, hours_ago, extras)
    ('water_leak', 'Hostel B', 'bathroom block', 'Water pipe leaking in the bathroom block, floor is wet.', 'medium', 'ASSIGNED', 20, {}),
    ('water_leak', 'Hostel B', '2nd floor corridor', 'Water dripping from the ceiling in the 2nd floor corridor.', 'medium', 'IN_PROGRESS', 18, {}),
    ('water_leak', 'Hostel B', 'ground floor tap', 'Tap near the ground floor keeps leaking and water pressure is very low.', 'medium', 'ASSIGNED', 10, {}),
    ('water_leak', 'Hostel B', 'laundry area', 'Water pooling in the laundry area, low water pressure again.', 'medium', 'ASSIGNED', 4, {}),
    ('broken_light', 'Block C', 'main staircase', 'Staircase light is out and the stairs are dark at night.', 'high', 'ASSIGNED', 13, {'overdue': True}),
    ('garbage_overflow', 'Mess Hall', 'back door', 'Garbage bin overflowing behind the mess.', 'medium', 'VERIFIED_CLOSED', 30, {'photos': 'garbage_overflow', 'verdict': 'verified', 'seed_no': 11}),
    ('blocked_path', 'Block D', '3rd floor corridor', 'Corridor blocked by stacked chairs and boxes.', 'medium', 'REOPENED', 26, {'photos': 'blocked_path', 'verdict': 'contradicted', 'seed_no': 12}),
    ('wifi_down', 'Central Library', 'reading hall', 'Wi-Fi in the reading hall is not connecting.', 'medium', 'CLOSURE_CLAIMED', 22, {}),
    ('other', 'Admin Block', 'ground floor lobby', 'Strange humming noise coming from the lobby ceiling.', 'medium', 'TRIAGED', 3, {'human': True}),
    ('pest', None, None, 'Cockroaches in the room, location not mentioned.', 'medium', 'NEEDS_INFO', 2, {}),
    ('broken_furniture', 'Canteen', 'outdoor seating', 'Two benches in the outdoor seating area are broken.', 'low', 'ASSIGNED', 6, {}),
    ('broken_light', 'Hostel A', 'corridor', 'Corridor tube light flickering for two days.', 'medium', 'VERIFIED_CLOSED', 40, {'photos': 'broken_light', 'verdict': 'verified', 'seed_no': 13}),
]


# A brand-new visitor's browser sends several requests at the same moment. Without this lock two of them both see
# "not seeded yet" and both try to write the marker, and the loser used to crash with a 500 (UNIQUE constraint failed).
_locks = defaultdict(threading.Lock)


def seed_workspace(db, workspace: str) -> int:
    key = 'seeded:' + workspace
    if db.get(Setting, key):
        return 0
    with _locks[workspace]:
        db.rollback()                              # end any open read so we see what another request just committed
        if db.get(Setting, key):
            return 0
        try:
            return _seed(db, workspace, key)
        except IntegrityError:                     # another worker process won the race: that is fine
            db.rollback()
            return 0


def _seed(db, workspace: str, key: str) -> int:
    now = real_now()
    n = 0
    for issue, building, detail, summary, urgency, end_state, hours_ago, extra in SEEDS:
        dept = config.DOMAIN['issue_types'][issue]['department']
        loc = ((building or '') + (', ' + detail if detail else '')).strip(', ') or None
        human = bool(extra.get('human'))
        t = Ticket(workspace=workspace, state='NEW', issue_type=issue, department=None if human else dept, urgency=urgency,
                   building=building, location_text=loc, summary=summary, original_text=None, language='en',
                   safety_hazard=urgency == 'high', missing_info=['location'] if not building else [],
                   followup_question='Which building or place on campus is this in?' if not building else None,
                   confidence=0.9 if not human else 0.35, needs_human=human, report_count=1, reporter_ids=[],
                   ai_source='demo', synthetic=True, created_at=now - timedelta(hours=hours_ago), updated_at=now)
        db.add(t)
        db.flush()
        note = {'note': 'SAMPLE DATA (synthetic), not produced by an AI model'}
        add_event(db, t.id, 'seed', 'CREATED', note)
        add_event(db, t.id, 'seed', 'INTAKE', {'result': {'issue_type': issue, 'urgency': urgency, 'summary': summary}, **note})
        if end_state == 'NEEDS_INFO':
            transition(db, t, 'NEEDS_INFO', 'pipeline', 'waiting for the reporter: location')
        else:
            transition(db, t, 'TRIAGED', 'pipeline', 'intake complete')
            if end_state != 'TRIAGED':
                set_due(t)
                t.due_at = t.created_at + (t.due_at - real_now()) if t.due_at else None
                if extra.get('overdue'):
                    t.due_at = now - timedelta(hours=5)
                transition(db, t, 'ASSIGNED', 'pipeline', 'routed to ' + dept)
        if extra.get('photos'):
            seed_no = extra['seed_no']
            kind = extra['photos']
            before = scene_jpeg(kind, False, seed_no, 'A', now - timedelta(hours=hours_ago))
            db.add(Image(ticket_id=t.id, workspace=workspace, kind='report', data=before, sha256='seed-' + str(t.id) + '-b',
                         phash=verify.phash_hex(before), exif_time=verify.exif_time(before), created_at=now))
            if extra['verdict'] == 'verified':
                after = scene_jpeg(kind, True, seed_no, 'A', now - timedelta(hours=1))
                db.add(Image(ticket_id=t.id, workspace=workspace, kind='after', data=after, sha256='seed-' + str(t.id) + '-a',
                             phash=verify.phash_hex(after), exif_time=None, created_at=now))
        if end_state in ('VERIFIED_CLOSED', 'REOPENED'):
            transition(db, t, 'CLOSURE_CLAIMED', 'department', 'department says the problem is fixed')
            checks = ([{'name': 'not_reused', 'passed': True, 'hard': True, 'detail': 'sample'}, {'name': 'fresh', 'passed': True, 'hard': True, 'detail': 'sample'},
                       {'name': 'state_ok', 'passed': True, 'hard': True, 'detail': 'sample'}, {'name': 'same_place', 'passed': True, 'hard': True, 'detail': 'sample'}]
                      if end_state == 'VERIFIED_CLOSED' else
                      [{'name': 'not_reused', 'passed': False, 'hard': True, 'detail': 'sample: the original photo was submitted again as the repair'},
                       {'name': 'fresh', 'passed': True, 'hard': True, 'detail': 'sample'}])
            add_event(db, t.id, 'verifier', 'GATE_RESULT', {'verdict': extra['verdict'], 'checks': checks, **note})
            t.last_verdict = extra['verdict']
            transition(db, t, end_state, 'verifier', 'gate verdict: ' + extra['verdict'])
        elif end_state == 'CLOSURE_CLAIMED':
            transition(db, t, 'CLOSURE_CLAIMED', 'department', 'department says the problem is fixed')
            add_event(db, t.id, 'verifier', 'AWAITING_CONFIRMATION', {'reason': 'Wi-Fi cannot be checked from a photo.', **note})
            t.last_verdict = 'awaiting_confirmation'
        elif end_state == 'IN_PROGRESS':
            transition(db, t, 'IN_PROGRESS', 'department', 'work started')
        n += 1
    db.add(Setting(key=key, value=real_now().isoformat()))
    db.commit()
    return n
