import pytest

from app import service
from app.pipeline import verify
from app.samples import sample_image


def chk(name, passed, hard):
    return {'name': name, 'passed': passed, 'hard': hard, 'detail': ''}


def test_verdict_all_pass():
    assert verify.verdict([chk('a', True, True), chk('b', True, False)]) == 'verified'


def test_verdict_hard_failure_is_contradicted():
    assert verify.verdict([chk('a', True, True), chk('b', False, True)]) == 'contradicted'


def test_verdict_soft_failure_needs_evidence():
    assert verify.verdict([chk('a', True, True), chk('b', False, False)]) == 'needs_evidence'


def test_hard_beats_soft():
    assert verify.verdict([chk('a', False, False), chk('b', False, True)]) == 'contradicted'


def test_explain_missing_lists_actions():
    tips = verify.explain_missing([chk('fresh', False, False), chk('state_ok', True, True)])
    assert len(tips) == 1 and 'camera' in tips[0]


def _open_ticket(db, ws, kind, seed):
    before = sample_image(kind + '__before', seed)
    res = service.create_report(db, ws, 'r1', 'Sample report about ' + kind.replace('_', ' ') + ' with the problem clearly visible', 'Hostel B', 'test spot', None, None, before)
    return res['ticket_id']


CASES = [
    ('after_genuine', 'verified'),
    ('after_reused', 'contradicted'),
    ('after_other_place', 'contradicted'),
    ('after_old', 'contradicted'),
    ('after_screenshot', 'needs_evidence'),
]


@pytest.mark.parametrize('kind', ['broken_light', 'water_leak', 'garbage_overflow'])
@pytest.mark.parametrize('evidence,expected', CASES)
def test_gate_verdicts_on_synthetic_scenes(db, ws, kind, evidence, expected):
    seed = 7
    tid = _open_ticket(db, ws, kind, seed)
    after = sample_image(kind + '__' + evidence, seed)
    out = service.claim_closure(db, ws, tid, 'department', after, '')
    assert out['verdict'] == expected, out['checks']
    expected_state = {'verified': 'VERIFIED_CLOSED', 'contradicted': 'REOPENED', 'needs_evidence': 'NEEDS_EVIDENCE'}[expected]
    assert out['ticket']['state'] == expected_state


def test_closure_without_photo_is_refused_for_visual_types(db, ws):
    tid = _open_ticket(db, ws, 'water_leak', 3)
    with pytest.raises(service.ServiceError):
        service.claim_closure(db, ws, tid, 'department', None, '')


def test_photo_reused_from_another_ticket_is_flagged(db, ws):
    t1 = _open_ticket(db, ws, 'water_leak', 21)
    after = sample_image('water_leak__after_genuine', 21)
    assert service.claim_closure(db, ws, t1, 'department', after, '')['verdict'] == 'verified'
    t2 = service.create_report(db, ws, 'r2', 'Another leak with water on the floor in the other bathroom', 'Hostel A', 'x', None, None, sample_image('water_leak__before', 22))['ticket_id']
    out = service.claim_closure(db, ws, t2, 'department', after, '')       # same repair photo submitted on a different ticket
    assert out['verdict'] == 'contradicted'
    assert any(c['name'] == 'not_reused' and not c['passed'] for c in out['checks'])


def test_non_visual_problem_needs_reporter_confirmation(db, ws):
    r = service.create_report(db, ws, 'r1', 'The wifi internet in my room is not working at all', 'Hostel A', 'room 12', None, None, None)
    tid = r['ticket_id']
    out = service.claim_closure(db, ws, tid, 'department', None, 'router replaced')
    assert out['verdict'] == 'awaiting_confirmation' and out['ticket']['state'] == 'CLOSURE_CLAIMED'
    done = service.reporter_confirm(db, ws, tid, 'reporter', True, '')
    assert done['state'] == 'VERIFIED_CLOSED'


def test_reporter_saying_fixed_does_not_close_a_photo_checked_ticket(db, ws):
    tid = _open_ticket(db, ws, 'water_leak', 5)
    out = service.reporter_confirm(db, ws, tid, 'reporter', True, 'looks fine')
    assert out['state'] != 'VERIFIED_CLOSED'
