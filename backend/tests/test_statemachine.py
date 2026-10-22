import pytest

from app.clock import real_now
from app.models import Event, Ticket
from app.pipeline.statemachine import ClosureNotAllowed, TransitionError, transition


def make_ticket(db, ws, state='NEW'):
    t = Ticket(workspace=ws, state=state, issue_type='broken_light', department='electrical', urgency='medium',
               summary='x', created_at=real_now(), updated_at=real_now())
    db.add(t)
    db.flush()
    return t


def test_valid_path_to_verified_closed(db, ws):
    t = make_ticket(db, ws)
    for to, actor in [('TRIAGED', 'pipeline'), ('ASSIGNED', 'pipeline'), ('IN_PROGRESS', 'department'),
                      ('CLOSURE_CLAIMED', 'department'), ('VERIFIED_CLOSED', 'verifier')]:
        transition(db, t, to, actor, 'test')
    assert t.state == 'VERIFIED_CLOSED'


def test_every_transition_is_logged(db, ws):
    t = make_ticket(db, ws)
    transition(db, t, 'TRIAGED', 'pipeline', 'x')
    transition(db, t, 'ASSIGNED', 'pipeline', 'x')
    assert db.query(Event).filter(Event.ticket_id == t.id, Event.type == 'STATE_CHANGED').count() == 2


def test_invalid_transition_rejected(db, ws):
    t = make_ticket(db, ws)
    with pytest.raises(TransitionError):
        transition(db, t, 'VERIFIED_CLOSED', 'verifier', 'skip everything')
    assert t.state == 'NEW'


@pytest.mark.parametrize('actor', ['department', 'pipeline', 'reporter', 'admin', 'ai_model', 'sla_clock'])
def test_unauthorized_actors_cannot_close(db, ws, actor):
    t = make_ticket(db, ws, 'CLOSURE_CLAIMED')
    with pytest.raises(ClosureNotAllowed):
        transition(db, t, 'VERIFIED_CLOSED', actor, 'please')
    assert t.state == 'CLOSURE_CLAIMED'


@pytest.mark.parametrize('actor', ['verifier', 'human_reviewer'])
def test_only_gate_or_human_can_close(db, ws, actor):
    t = make_ticket(db, ws, 'CLOSURE_CLAIMED')
    transition(db, t, 'VERIFIED_CLOSED', actor, 'ok')
    assert t.state == 'VERIFIED_CLOSED'


def test_closed_ticket_can_only_reopen(db, ws):
    t = make_ticket(db, ws, 'VERIFIED_CLOSED')
    with pytest.raises(TransitionError):
        transition(db, t, 'ASSIGNED', 'pipeline', 'x')
    transition(db, t, 'REOPENED', 'reporter', 'disputed')
    assert t.state == 'REOPENED'
