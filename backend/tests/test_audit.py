from app.clock import real_now
from app.models import Event, Ticket
from app.pipeline.audit import add_event, verify_chain
from app.pipeline.statemachine import transition
from app.service import delete_my_data


def build(db, ws):
    t = Ticket(workspace=ws, state='NEW', issue_type='water_leak', department='plumbing', urgency='medium',
               summary='leak', original_text='secret words', created_at=real_now(), updated_at=real_now())
    db.add(t)
    db.flush()
    add_event(db, t.id, 'reporter', 'CREATED', {'a': 1})
    transition(db, t, 'TRIAGED', 'pipeline', 'x')
    transition(db, t, 'ASSIGNED', 'pipeline', 'x')
    db.commit()
    return t


def test_clean_chain_verifies(db, ws):
    t = build(db, ws)
    ok, msg, n = verify_chain(db, t.id)
    assert ok and n == 3 and msg == 'chain intact'


def test_edited_payload_is_detected(db, ws):
    t = build(db, ws)
    ev = db.query(Event).filter(Event.ticket_id == t.id, Event.seq == 1).one()
    ev.payload = {'a': 999}
    db.commit()
    ok, msg, _ = verify_chain(db, t.id)
    assert not ok and 'payload edited at event 1' in msg


def test_edited_metadata_breaks_chain(db, ws):
    t = build(db, ws)
    ev = db.query(Event).filter(Event.ticket_id == t.id, Event.seq == 2).one()
    ev.actor = 'someone_else'
    db.commit()
    ok, msg, _ = verify_chain(db, t.id)
    assert not ok and 'event 2' in msg


def test_removed_event_is_detected(db, ws):
    t = build(db, ws)
    db.query(Event).filter(Event.ticket_id == t.id, Event.seq == 2).delete()
    db.commit()
    ok, msg, _ = verify_chain(db, t.id)
    assert not ok


def test_privacy_deletion_keeps_chain_valid(db, ws):
    t = build(db, ws)
    result = delete_my_data(db, ws, t.id)
    assert result['deleted'] and result['chain_still_valid']
    db.refresh(t)
    assert t.original_text is None
    assert all(e.payload is None for e in db.query(Event).filter(Event.ticket_id == t.id).all())
    assert verify_chain(db, t.id)[0]
