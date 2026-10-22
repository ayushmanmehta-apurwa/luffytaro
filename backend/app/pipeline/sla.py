"""SLA deadlines and escalation. The demo clock is per workspace and only affects *when we evaluate*
deadlines; real timestamps are never altered."""
from datetime import timedelta

from .. import config
from ..clock import get_offset_hours, real_now, sla_now
from ..models import Ticket
from .audit import add_event
from .statemachine import OPEN_STATES

ESCALATION_TARGETS = ['department supervisor', 'department head', 'registrar office']


def sla_hours(department: str, urgency: str) -> int:
    return config.DOMAIN['departments'][department]['sla_hours'][urgency]


def set_due(ticket) -> None:
    if ticket.department:
        ticket.due_at = real_now() + timedelta(hours=sla_hours(ticket.department, ticket.urgency))


def sla_tick(db, workspace: str) -> int:
    """Escalate every open ticket past its deadline. Returns the number of escalations made."""
    now = sla_now(db, workspace)
    offset = get_offset_hours(db, workspace)
    count = 0
    q = db.query(Ticket).filter(Ticket.workspace == workspace, Ticket.state.in_(OPEN_STATES),
                                Ticket.due_at.isnot(None), Ticket.due_at < now)
    for t in q.all():
        t.escalation_level += 1
        hours = sla_hours(t.department, t.urgency)
        t.due_at = now + timedelta(hours=max(1, hours // 2))
        target = ESCALATION_TARGETS[min(t.escalation_level - 1, len(ESCALATION_TARGETS) - 1)]
        add_event(db, t.id, 'sla_clock', 'ESCALATED', {
            'level': t.escalation_level, 'notify': target,
            'simulated': offset != 0, 'sample_data': bool(t.synthetic), 'demo_clock_offset_hours': offset,
            'note': ('Escalation caused by the demo clock; not a real service failure.' if offset
                     else 'Sample ticket (synthetic data).' if t.synthetic else 'Real deadline passed.')})
        count += 1
    db.flush()
    return count


def sla_status(ticket, now) -> dict:
    if not ticket.due_at or ticket.state not in OPEN_STATES:
        return {'seconds_remaining': None, 'overdue': False}
    secs = int((ticket.due_at - now).total_seconds())
    return {'seconds_remaining': secs, 'overdue': secs < 0}
