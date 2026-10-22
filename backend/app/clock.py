"""Time helpers.

Real timestamps (tickets, events, photos) always use real UTC time.
The *demo clock* only shifts the moment SLA deadlines are evaluated, per workspace, so a demo can
show an escalation without waiting days. Escalations caused by it are flagged simulated=True and are
excluded from any real service-performance figure.
"""
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from .models import Setting

_write_lock = threading.Lock()


def real_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _key(workspace: str) -> str:
    return 'clock_offset_hours:' + workspace


def get_offset_hours(db, workspace: str) -> float:
    row = db.get(Setting, _key(workspace))
    return float(row.value) if row else 0.0


def set_offset_hours(db, workspace: str, hours: float) -> None:
    """Insert-or-update that is safe when several requests set the clock at once."""
    with _write_lock:
        for _attempt in range(2):
            row = db.get(Setting, _key(workspace))
            if row:
                row.value = str(hours)
                break
            try:
                db.add(Setting(key=_key(workspace), value=str(hours)))
                db.flush()
                break
            except IntegrityError:               # another process inserted it first: loop once more and update it
                db.rollback()
    db.flush()


def sla_now(db, workspace: str) -> datetime:
    return real_now() + timedelta(hours=get_offset_hours(db, workspace))
