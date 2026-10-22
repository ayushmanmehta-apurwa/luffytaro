"""SHA-256 hash-chained audit log.

Each event stores the hash of the previous event, so editing history breaks the chain. The payload is
hashed separately (payload_sha256) and the chain is built over that hash, so the privacy control can
blank a payload without breaking verification.

HONEST LIMIT: this is tamper-EVIDENT, not tamper-PROOF. Someone with full database control could
rebuild the whole chain. Publishing the latest chain hash somewhere outside the database
(for example in a commit message) makes that much harder.
"""
import hashlib
import json

from ..clock import real_now
from ..models import Event


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), default=str)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _chain_input(prev, ticket_id, seq, ts, actor, type_, payload_sha256):
    return prev + canonical({'t': ticket_id, 'seq': seq, 'ts': ts, 'actor': actor, 'type': type_,
                             'payload_sha256': payload_sha256})


def add_event(db, ticket_id: int, actor: str, type_: str, payload: dict | None):
    last = db.query(Event).filter(Event.ticket_id == ticket_id).order_by(Event.seq.desc()).first()
    seq = last.seq + 1 if last else 1
    prev = last.hash if last else 'GENESIS'
    ts = real_now().isoformat()
    payload = json.loads(canonical(payload or {}))          # make it JSON-safe and stable
    psha = sha(canonical(payload))
    h = sha(_chain_input(prev, ticket_id, seq, ts, actor, type_, psha))
    ev = Event(ticket_id=ticket_id, seq=seq, ts=ts, actor=actor, type=type_, payload=payload,
               payload_sha256=psha, prev_hash=prev, hash=h)
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db, ticket_id: int):
    """Returns (ok: bool, message: str, event_count: int)."""
    prev = 'GENESIS'
    events = db.query(Event).filter(Event.ticket_id == ticket_id).order_by(Event.seq).all()
    for ev in events:
        if ev.payload is not None and sha(canonical(ev.payload)) != ev.payload_sha256:
            return False, 'payload edited at event ' + str(ev.seq), len(events)
        expect = sha(_chain_input(prev, ticket_id, ev.seq, ev.ts, ev.actor, ev.type, ev.payload_sha256))
        if ev.prev_hash != prev or ev.hash != expect:
            return False, 'chain broken at event ' + str(ev.seq), len(events)
        prev = ev.hash
    return True, 'chain intact', len(events)
