"""The only code that may change a ticket's state.

AI models never call this. The pipeline validates a model's answer first, then calls transition().
"""
from ..clock import real_now
from .audit import add_event

ALLOWED = {
    'NEW': {'NEEDS_INFO', 'TRIAGED'},
    'NEEDS_INFO': {'TRIAGED', 'ASSIGNED'},
    'TRIAGED': {'ASSIGNED'},
    'ASSIGNED': {'IN_PROGRESS', 'CLOSURE_CLAIMED'},
    'IN_PROGRESS': {'CLOSURE_CLAIMED'},
    'CLOSURE_CLAIMED': {'VERIFIED_CLOSED', 'NEEDS_EVIDENCE', 'REOPENED'},
    'NEEDS_EVIDENCE': {'CLOSURE_CLAIMED', 'VERIFIED_CLOSED', 'REOPENED'},
    'REOPENED': {'ASSIGNED', 'IN_PROGRESS'},
    'VERIFIED_CLOSED': {'REOPENED'},
}
# The ONLY actors allowed to move a ticket into VERIFIED_CLOSED.
CAN_CLOSE = {'verifier', 'human_reviewer'}
OPEN_STATES = ['NEW', 'NEEDS_INFO', 'TRIAGED', 'ASSIGNED', 'IN_PROGRESS', 'CLOSURE_CLAIMED', 'NEEDS_EVIDENCE', 'REOPENED']


class TransitionError(ValueError):
    pass


class ClosureNotAllowed(PermissionError):
    pass


def transition(db, ticket, to_state: str, actor: str, reason: str, extra: dict | None = None):
    if to_state not in ALLOWED.get(ticket.state, set()):
        raise TransitionError(ticket.state + ' -> ' + to_state + ' is not an allowed transition')
    if to_state == 'VERIFIED_CLOSED' and actor not in CAN_CLOSE:
        raise ClosureNotAllowed('only the verification gate or a human reviewer can close a ticket (actor: ' + actor + ')')
    old = ticket.state
    ticket.state = to_state
    ticket.updated_at = real_now()
    payload = {'from': old, 'to': to_state, 'reason': reason}
    if extra:
        payload.update(extra)
    add_event(db, ticket.id, actor, 'STATE_CHANGED', payload)
