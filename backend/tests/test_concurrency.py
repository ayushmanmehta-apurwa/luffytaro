"""A new visitor's browser fires many requests at once. These tests reproduce that."""
import threading
import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Setting, Ticket
from app.seed import SEEDS, seed_workspace


def run_parallel(n, fn):
    errors, barrier = [], threading.Barrier(n)

    def worker(i):
        try:
            barrier.wait()
            fn(i)
        except Exception as e:  # noqa: BLE001 - we want to see every kind of failure
            errors.append(repr(e))
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return errors


def test_parallel_seeding_of_one_new_workspace_creates_exactly_one_set():
    ws = 'race-' + uuid.uuid4().hex[:8]

    def seed(_):
        with SessionLocal() as db:
            seed_workspace(db, ws)
    assert run_parallel(8, seed) == []
    with SessionLocal() as db:
        assert db.query(Ticket).filter(Ticket.workspace == ws).count() == len(SEEDS)
        assert db.query(Setting).filter(Setting.key == 'seeded:' + ws).count() == 1


def test_parallel_first_requests_from_a_new_browser_all_succeed():
    ws = 'race-' + uuid.uuid4().hex[:8]
    statuses = []

    def hit(i):
        with TestClient(app) as c:                # one client per thread, like separate browser connections
            h = {'X-Workspace': ws, 'X-Role': 'reporter', 'X-Reporter': 'r' + str(i)}
            paths = ['/api/tickets', '/api/tickets?mine=true', '/api/hotspots', '/api/tickets']
            statuses.extend(c.get(p, headers=h).status_code for p in paths)
    assert run_parallel(6, hit) == []
    assert statuses and set(statuses) == {200}
    with SessionLocal() as db:
        assert db.query(Ticket).filter(Ticket.workspace == ws).count() == len(SEEDS)


def test_parallel_report_submissions_from_a_brand_new_workspace():
    ws = 'race-' + uuid.uuid4().hex[:8]
    codes = []

    def submit(i):
        with TestClient(app) as c:
            h = {'X-Workspace': ws, 'X-Role': 'reporter', 'X-Reporter': 'r' + str(i)}
            codes.append(c.post('/api/reports', headers=h, data={'text': 'Water pipe is leaking badly in room ' + str(i), 'building': 'Hostel A'}).status_code)
            codes.append(c.get('/api/tickets', headers=h).status_code)
    assert run_parallel(5, submit) == []
    assert set(codes) == {200}


def test_demo_clock_can_be_set_repeatedly_and_in_parallel(client, ws):
    h = {'X-Workspace': ws, 'X-Role': 'admin'}
    client.get('/api/stats', headers=h)           # creates the workspace first
    results = []

    def advance(_):
        with TestClient(app) as c:
            results.append(c.post('/api/admin/advance_clock?hours=1', headers=h).status_code)
    assert run_parallel(4, advance) == []
    assert set(results) == {200}
