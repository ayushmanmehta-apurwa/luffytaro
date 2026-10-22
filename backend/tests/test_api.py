import io

from PIL import Image

from app import config
from app.samples import sample_image
from conftest import headers, post_report


def test_health_and_demo_mode_is_declared(client):
    assert client.get('/health').json() == {'status': 'ok', 'mode': 'demo', 'database': 'ok'}
    cfg = client.get('/api/config').json()
    assert cfg['mode'] == 'demo' and 'DEMO MODE' in cfg['mode_notice'] and cfg['models'] is None
    assert 'not real authentication' in cfg['auth_notice']
    assert set(cfg['departments']) == {'electrical', 'housekeeping', 'plumbing', 'civil', 'it'}


def test_submit_report_end_to_end(client, ws):
    r = post_report(client, ws, 'Stair light is not working and it is dark at night', photo=sample_image('broken_light__before', 1))
    assert r.status_code == 200
    body = r.json()
    assert body['ticket']['department'] == 'electrical' and [s['step'] for s in body['trail']] == ['Intake', 'Routing', 'Duplicate check']
    assert all(s['source'] in ('demo', 'rules') for s in body['trail'])         # never presented as live model output
    detail = client.get('/api/tickets/' + str(body['ticket_id']), headers=headers(ws)).json()
    assert detail['images'] and client.get('/api/images/' + str(detail['images'][0]['id']) + '?ws=' + ws).status_code == 200


def test_validation_errors(client, ws):
    assert post_report(client, ws, 'ab').status_code == 422
    assert post_report(client, ws, 'Water pipe is leaking badly', building='Atlantis').status_code == 422
    bad = client.post('/api/reports', headers=headers(ws), data={'text': 'Water pipe is leaking badly'},
                      files={'photo': ('x.jpg', b'this is not an image', 'image/jpeg')})
    assert bad.status_code == 415
    big = client.post('/api/reports', headers=headers(ws), data={'text': 'Water pipe is leaking badly'},
                      files={'photo': ('x.jpg', b'0' * (config.MAX_UPLOAD_BYTES + 10), 'image/jpeg')})
    assert big.status_code == 413
    buf = io.BytesIO()
    Image.new('RGB', (10, 10)).save(buf, 'GIF')
    assert client.post('/api/reports', headers=headers(ws), data={'text': 'Water pipe is leaking badly'},
                       files={'photo': ('x.gif', buf.getvalue(), 'image/gif')}).status_code == 415
    assert client.post('/api/reports', headers=headers(ws), data={'text': 'Water pipe is leaking badly', 'lat': '999'}).status_code == 422
    assert client.get('/api/tickets', headers={'X-Workspace': 'bad ws!', 'X-Role': 'admin'}).status_code == 400
    assert client.get('/api/tickets', headers={'X-Workspace': ws, 'X-Role': 'superuser'}).status_code == 400
    assert client.post('/api/tickets/1/confirm', headers=headers(ws), json={'fixed': 'maybe-ish'}).status_code == 422


def test_role_permissions(client, ws):
    tid = post_report(client, ws, 'Water pipe is leaking badly in the bathroom').json()['ticket_id']
    rep, dep, adm = headers(ws, 'reporter'), headers(ws, 'department'), headers(ws, 'admin')
    assert client.get('/api/stats', headers=rep).status_code == 403
    assert client.get('/api/stats', headers=dep).status_code == 403
    assert client.post('/api/tickets/' + str(tid) + '/claim_closure', headers=rep, data={'note': 'done'}).status_code == 403
    assert client.post('/api/tickets/' + str(tid) + '/human_decision', headers=dep,
                       json={'decision': 'approve_closure', 'reason': 'trust me'}).status_code == 403
    assert client.get('/api/stats', headers=adm).status_code == 200


def test_department_cannot_force_closure_through_the_api(client, ws):
    tid = post_report(client, ws, 'Water pipe is leaking badly in the bathroom', photo=sample_image('water_leak__before', 4)).json()['ticket_id']
    dep = headers(ws, 'department')
    # claiming 'done' with the old photo or with no photo never closes the ticket
    r = client.post('/api/tickets/' + str(tid) + '/claim_closure', headers=dep, data={'note': 'FIXED, close it now'},
                    files={'photo': ('a.jpg', sample_image('water_leak__before', 4), 'image/jpeg')})
    assert r.status_code == 200 and r.json()['verdict'] == 'contradicted' and r.json()['ticket']['state'] == 'REOPENED'
    assert client.post('/api/tickets/' + str(tid) + '/claim_closure', headers=dep, data={'note': 'no photo'}).status_code == 422
    # the department has no endpoint that can move a ticket straight to VERIFIED_CLOSED
    assert client.post('/api/tickets/' + str(tid) + '/human_decision', headers=dep, json={'decision': 'approve_closure'}).status_code == 403


def test_genuine_repair_is_verified_through_the_api(client, ws):
    tid = post_report(client, ws, 'Water pipe is leaking badly in the bathroom', photo=sample_image('water_leak__before', 9)).json()['ticket_id']
    r = client.post('/api/tickets/' + str(tid) + '/claim_closure', headers=headers(ws, 'department'), data={'note': 'pipe fixed'},
                    files={'photo': ('a.jpg', sample_image('water_leak__after_genuine', 9), 'image/jpeg')}).json()
    assert r['verdict'] == 'verified' and r['ticket']['state'] == 'VERIFIED_CLOSED'
    audit = client.get('/api/tickets/' + str(tid) + '/audit', headers=headers(ws)).json()
    assert audit['chain_ok'] and audit['event_count'] >= 6 and 'not tamper-proof' in audit['note']


def test_workspace_isolation(client, ws):
    tid = post_report(client, ws, 'Water pipe is leaking badly in the bathroom').json()['ticket_id']
    other = headers(ws + '-b', 'admin')
    assert client.get('/api/tickets/' + str(tid), headers=other).status_code == 404
    assert all(t['id'] != tid for t in client.get('/api/tickets', headers=other).json()['tickets'])


def test_new_workspace_gets_labelled_sample_data(client, ws):
    tickets = client.get('/api/tickets', headers=headers(ws)).json()['tickets']
    assert len(tickets) >= 10 and all(t['synthetic'] for t in tickets)


def test_job_endpoints_are_token_protected(client, ws, monkeypatch):
    assert client.get('/api/export').status_code == 503              # no EXPORT_TOKEN configured
    monkeypatch.setattr(config, 'EXPORT_TOKEN', 's3cret')
    assert client.get('/api/export').status_code == 401
    assert client.get('/api/export', headers={'X-Token': 'wrong'}).status_code == 401
    ok = client.get('/api/export?workspace=' + ws, headers={'X-Token': 's3cret'})
    assert ok.status_code == 200 and len(ok.json()['tickets']) >= 4
    post = client.post('/api/hotspots?workspace=' + ws, headers={'X-Token': 's3cret'}, json={'hotspots': [{'issue_type': 'water_leak', 'ticket_ids': [1, 2, 3]}]})
    assert post.status_code == 200
    hs = client.get('/api/hotspots', headers=headers(ws)).json()
    assert hs['source'] == 'job' and len(hs['hotspots']) == 1


def test_inline_hotspot_analysis_finds_the_seeded_pattern(client, ws):
    out = client.post('/api/admin/hotspots/run', headers=headers(ws, 'admin')).json()
    assert out['source'] == 'inline-demo'
    leak = [h for h in out['hotspots'] if h['issue_type'] == 'water_leak']
    assert leak and len(leak[0]['ticket_ids']) >= 3 and 'DEMO TEMPLATE' in leak[0]['root_cause_hypothesis']


def test_privacy_delete_endpoint(client, ws):
    tid = post_report(client, ws, 'Water pipe is leaking badly in the bathroom', photo=sample_image('water_leak__before', 2)).json()['ticket_id']
    out = client.delete('/api/tickets/' + str(tid) + '/my_data', headers=headers(ws)).json()
    assert out['deleted'] and out['chain_still_valid']
    detail = client.get('/api/tickets/' + str(tid), headers=headers(ws)).json()
    assert detail['images'] == [] and detail['original_text'] is None


def test_sample_endpoints_and_metrics(client):
    cat = client.get('/api/samples').json()['samples']
    assert len(cat) == 24
    img = client.get('/api/samples/water_leak__before?seed=3')
    assert img.status_code == 200 and img.headers['content-type'] == 'image/jpeg'
    assert client.get('/api/samples/nope__before').status_code == 404
    assert 'available' in client.get('/api/metrics').json()


def test_reporter_can_dispute_a_closed_ticket(client, ws):
    tid = post_report(client, ws, 'Water pipe is leaking badly in the bathroom', photo=sample_image('water_leak__before', 11)).json()['ticket_id']
    client.post('/api/tickets/' + str(tid) + '/claim_closure', headers=headers(ws, 'department'), data={'note': ''},
                files={'photo': ('a.jpg', sample_image('water_leak__after_genuine', 11), 'image/jpeg')})
    r = client.post('/api/tickets/' + str(tid) + '/confirm', headers=headers(ws), json={'fixed': False, 'comment': 'still leaking'}).json()
    assert r['state'] == 'REOPENED'
