from datetime import timedelta

from app import service
from app.clock import get_offset_hours, real_now
from app.models import Event, Ticket
from app.pipeline.sla import sla_tick


def test_demo_clock_escalates_and_is_flagged_simulated(client, ws):
    h = {'X-Workspace': ws, 'X-Role': 'admin'}
    r = client.post('/api/reports', headers={'X-Workspace': ws, 'X-Role': 'reporter', 'X-Reporter': 'x'},
                    data={'text': 'Water pipe is leaking and floor is wet', 'building': 'Hostel B'}).json()
    tid = r['ticket_id']
    created = client.get('/api/tickets/' + str(tid), headers=h).json()['created_at']
    out = client.post('/api/admin/advance_clock?hours=30', headers=h).json()
    assert out['escalations_made'] >= 1 and out['demo_clock_offset_hours'] == 30
    detail = client.get('/api/tickets/' + str(tid), headers=h).json()
    esc = [e for e in detail['events'] if e['type'] == 'ESCALATED']
    assert esc and esc[0]['payload']['simulated'] is True and esc[0]['payload']['notify'] == 'department supervisor'
    assert detail['created_at'] == created                      # real timestamps untouched
    stats = client.get('/api/stats', headers=h).json()
    assert stats['escalations_simulated'] >= 1 and stats['escalations_real'] == 0


def test_demo_clock_is_per_workspace(client, ws):
    other = ws + '-other'
    client.post('/api/admin/advance_clock?hours=50', headers={'X-Workspace': ws, 'X-Role': 'admin'})
    other_cfg = client.get('/api/stats', headers={'X-Workspace': other, 'X-Role': 'admin'}).json()
    assert other_cfg['demo_clock_offset_hours'] == 0


def test_real_overdue_escalates_without_simulation(db, ws):
    r = service.create_report(db, ws, 'r', 'Water pipe is leaking and the floor is wet', 'Hostel B', '', None, None, None)
    t = db.get(Ticket, r['ticket_id'])
    t.due_at = real_now() - timedelta(hours=1)
    db.commit()
    assert sla_tick(db, ws) == 1
    ev = db.query(Event).filter(Event.ticket_id == t.id, Event.type == 'ESCALATED').one()
    assert ev.payload['simulated'] is False and get_offset_hours(db, ws) == 0


def test_closed_tickets_do_not_escalate(db, ws):
    r = service.create_report(db, ws, 'r', 'Water pipe is leaking and the floor is wet', 'Hostel B', '', None, None, None)
    t = db.get(Ticket, r['ticket_id'])
    t.state, t.due_at = 'VERIFIED_CLOSED', real_now() - timedelta(hours=9)
    db.commit()
    assert sla_tick(db, ws) == 0


def test_reporter_cannot_use_demo_clock(client, ws):
    r = client.post('/api/admin/advance_clock?hours=5', headers={'X-Workspace': ws, 'X-Role': 'reporter'})
    assert r.status_code == 403
