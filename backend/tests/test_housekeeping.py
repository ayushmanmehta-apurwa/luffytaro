from datetime import timedelta

from app import service
from app.clock import real_now
from app.models import Image, Setting, Ticket, Usage
from app.seed import seed_workspace
from conftest import headers


def test_health_reports_the_database(client):
    r = client.get('/health')
    assert r.status_code == 200 and r.json()['database'] == 'ok'


def test_listing_tickets_reads_the_clock_once_not_per_ticket(client, ws, monkeypatch):
    calls = {'n': 0}
    real = service.get_offset_hours

    def counting(db, w):
        calls['n'] += 1
        return real(db, w)
    monkeypatch.setattr(service, 'get_offset_hours', counting)
    tickets = client.get('/api/tickets', headers=headers(ws)).json()['tickets']
    assert len(tickets) >= 10 and calls['n'] <= 2


def test_old_untouched_workspaces_are_purged_and_recent_ones_kept(db, ws):
    old, fresh = ws + '-old', ws + '-fresh'
    for w in (old, fresh):
        seed_workspace(db, w)
    stale = real_now() - timedelta(days=30)
    db.query(Setting).filter(Setting.key == 'seeded:' + old).update({'value': stale.isoformat()})
    db.query(Ticket).filter(Ticket.workspace == old).update({'updated_at': stale})
    db.add(Usage(ts=stale, workspace=old, step='x', model='m', total_tokens=1, latency_s=0.1, ok=True))
    db.commit()
    assert db.query(Ticket).filter(Ticket.workspace == old).count() > 0
    n = service.purge_old_workspaces(db, 14)
    assert n >= 1
    assert db.query(Ticket).filter(Ticket.workspace == old).count() == 0
    assert db.query(Image).filter(Image.workspace == old).count() == 0
    assert db.query(Usage).filter(Usage.workspace == old).count() == 0
    assert db.query(Ticket).filter(Ticket.workspace == fresh).count() > 0


def test_a_recently_used_old_workspace_is_not_purged(db, ws):
    seed_workspace(db, ws)
    db.query(Setting).filter(Setting.key == 'seeded:' + ws).update({'value': (real_now() - timedelta(days=40)).isoformat()})
    db.commit()                                    # created long ago, but its tickets were touched just now
    service.purge_old_workspaces(db, 14)
    assert db.query(Ticket).filter(Ticket.workspace == ws).count() > 0


def test_purge_can_be_disabled(db, ws):
    seed_workspace(db, ws)
    assert service.purge_old_workspaces(db, 0) == 0
