"""Evaluation harness. Compares CivicClosure with simple baselines on SYNTHETIC data and writes
eval/results/metrics.json (shown in the Admin dashboard).

  python eval/make_dataset.py           # once, creates eval/data/reports.jsonl
  python eval/run_eval.py               # runs in whatever mode your .env selects

DEMO mode measures the deterministic rules and image statistics, NOT NVIDIA model performance. LIVE mode uses
your Nebius credits (roughly 2-4 model calls per report; use --limit to try a small run first).
Tune thresholds on the dev half and read results from the test half only.
"""
import argparse
import json
import statistics
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'eval'))
import os
os.environ.setdefault('DATABASE_URL', 'sqlite:///' + str(ROOT / 'eval' / 'results' / 'eval.db'))

from sklearn.metrics import accuracy_score, f1_score  # noqa: E402

from app import config, samples, service  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
import baseline  # noqa: E402


def load_rows():
    path = ROOT / 'eval' / 'data' / 'reports.jsonl'
    if not path.exists():
        sys.exit('Run python eval/make_dataset.py first.')
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


def split_half(rows):
    """Deterministic 50/50 dev/test split by row id (tune on dev, report on test)."""
    return [r for r in rows if r['id'] % 2 == 0], [r for r in rows if r['id'] % 2 == 1]


def coverage_curve(pairs):
    pairs = sorted(pairs, key=lambda p: -p[0])
    step = max(1, len(pairs) // 20)
    return [{'coverage': round(k / len(pairs), 2), 'accuracy': round(sum(c for _, c in pairs[:k]) / k, 3)} for k in range(step, len(pairs) + 1, step)]


def closure_rates(cases, key):
    fake = [c for c in cases if c['truth'] == 'fake']
    real = [c for c in cases if c['truth'] == 'genuine']
    accepted = [c for c in cases if c[key] == 'verified']
    return {'false_accept_rate': sum(c[key] == 'verified' for c in fake) / len(fake) if fake else None,
            'false_reject_rate': sum(c[key] != 'verified' for c in real) / len(real) if real else None,
            'closure_precision': (sum(c['truth'] == 'genuine' for c in accepted) / len(accepted)) if accepted else None,
            'n_fake': len(fake), 'n_genuine': len(real), 'verdicts': dict(Counter(c[key] for c in cases))}


def eval_routing(db, rows, ws):
    """Run each report through intake + triage (no tickets created) and through the baseline."""
    from app.pipeline import intake as intake_mod, triage as triage_mod
    results, lat, tokens = [], [], 0
    for r in rows:
        t0 = time.time()
        intake, m1 = intake_mod.run_intake(db, ws, r['text'], r.get('building'), r.get('detail'), None)
        route, m2 = triage_mod.triage(db, ws, intake)
        lat.append(time.time() - t0)
        tokens += (m1.get('tokens') or 0) + (m2.get('tokens') or 0)
        b_issue, b_dept = baseline.routing_baseline(r['text'])
        results.append({'row': r, 'issue': route.issue_type, 'dept': route.department, 'human': route.needs_human, 'conf': route.confidence,
                        'b_issue': b_issue, 'b_dept': b_dept})
    return results, lat, tokens


def scored(results, issue_key, dept_key):
    gold = [r['row']['gold_department'] for r in results]
    pred = [r[dept_key] for r in results]
    gi = [r['row']['gold_issue_type'] for r in results]
    pi = [r[issue_key] for r in results]
    return {'accuracy': accuracy_score(gi, pi), 'macro_f1': f1_score(gi, pi, average='macro'), 'department_accuracy': accuracy_score([g or 'none' for g in gold], [p or 'none' for p in pred]), 'n': len(results)}


def eval_duplicates(db, rows, ws):
    """Stream reports into a fresh workspace; every report that joins an existing ticket is a predicted duplicate."""
    from itertools import combinations
    normal = [r for r in rows if r['kind'] == 'normal']
    ticket_of, pred_pairs, tp = {}, set(), 0
    for r in normal:
        out = service.create_report(db, ws, 'eval', r['text'], r.get('building'), r.get('detail'), None, None, None)
        tid = out.get('merged_into') or out['ticket_id']
        ticket_of[r['id']] = tid
    gold_pairs = {frozenset((a['id'], b['id'])) for a, b in combinations(normal, 2) if a['dup_group'] == b['dup_group']}
    pred_pairs = {frozenset((a['id'], b['id'])) for a, b in combinations(normal, 2) if ticket_of[a['id']] == ticket_of[b['id']]}
    tp = len(gold_pairs & pred_pairs)
    prec = tp / len(pred_pairs) if pred_pairs else None
    rec = tp / len(gold_pairs) if gold_pairs else None
    f1 = (2 * prec * rec / (prec + rec)) if prec and rec else 0.0
    return {'precision': prec, 'recall': rec, 'f1': f1, 'gold_pairs': len(gold_pairs), 'predicted_pairs': len(pred_pairs)}


def eval_closure(db, ws, per_kind):
    # Every case gets its own workspace so cases cannot merge as duplicates or trip each other's reuse check.
    """Synthetic closure cases built in memory from generated scenes. Genuine repairs vs five kinds of fake evidence."""
    cases = []
    ev = ['after_genuine', 'after_reused', 'after_other_place', 'after_old', 'after_screenshot']
    for kind in samples.KINDS:
        for s in range(1, per_kind + 1):
            for e in ev:
                seed = 1000 * (ev.index(e) + 1) + s + 10 * samples.KINDS.index(kind)
                before = samples.sample_image(kind + '__before', seed)
                case_ws = ws + '-' + str(len(cases))
                rep = service.create_report(db, case_ws, 'eval', 'Sample report about ' + kind.replace('_', ' ') + ' clearly visible in the photo', 'Hostel B', 'case ' + str(seed), None, None, before)
                tid = rep['ticket_id']
                t0 = time.time()
                out = service.claim_closure(db, case_ws, tid, 'department', samples.sample_image(kind + '__' + e, seed), 'claimed fixed')
                cases.append({'kind': kind, 'evidence': e, 'truth': 'genuine' if e == 'after_genuine' else 'fake',
                              'civic': out['verdict'], 'baseline': baseline.trust_resolved_closure(None), 'latency': time.time() - t0})
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='only use the first N reports (cheap live smoke test)')
    ap.add_argument('--closure-per-kind', type=int, default=6, help='synthetic closure scenes per issue type (x5 evidence kinds)')
    ap.add_argument('--split', choices=['test', 'dev', 'all'], default='test')
    args = ap.parse_args()

    init_db()
    rows = load_rows()
    dev, test = split_half(rows)
    use = {'test': test, 'dev': dev, 'all': rows}[args.split]
    if args.limit:
        use = use[:args.limit]
    live = config.is_live()
    ws = 'eval-' + uuid.uuid4().hex[:8]
    print('mode:', 'LIVE (NVIDIA models via Nebius)' if live else 'DEMO (deterministic rules)', '| split:', args.split, '| reports:', len(use))

    with SessionLocal() as db:
        res, lat, toks = eval_routing(db, use, ws)
        db.commit()
        normal = [r for r in res if r['row']['kind'] == 'normal']
        routing, base_routing = scored(normal, 'issue', 'dept'), scored(normal, 'b_issue', 'b_dept')
        human_rate = sum(r['human'] for r in res) / len(res)
        curve = coverage_curve([(r['conf'], r['issue'] == r['row']['gold_issue_type']) for r in normal])

        # injection: does appending a malicious instruction change routing compared with the clean text?
        inj = [r for r in res if r['row']['kind'] == 'injection']
        changed = 0
        from app.pipeline import intake as intake_mod, triage as triage_mod
        for r in inj:
            clean_intake, _ = intake_mod.run_intake(db, ws, r['row']['clean_text'], r['row'].get('building'), r['row'].get('detail'), None)
            clean_route, _ = triage_mod.triage(db, ws, clean_intake)
            if (clean_route.department, clean_route.issue_type) != (r['dept'], r['issue']):
                changed += 1

        dup_rows = [r for r in use if r['kind'] == 'normal']
        dup = eval_duplicates(db, dup_rows, ws + '-dup') if len(dup_rows) > 3 else None
        cases = eval_closure(db, ws + '-closure', max(1, args.closure_per_kind if not args.limit else 1))
        db.commit()

    civic, base = closure_rates(cases, 'civic'), closure_rates(cases, 'baseline')
    civic['baseline'] = base
    by_evidence = {e: dict(Counter(c['civic'] for c in cases if c['evidence'] == e)) for e in sorted({c['evidence'] for c in cases})}
    metrics = {
        'mode': 'live' if live else 'demo', 'generated_at': datetime.now(timezone.utc).replace(tzinfo=None).isoformat(), 'split': args.split, 'synthetic': True,
        'note': ('SYNTHETIC test data (generated reports, generated illustration scenes). ' +
                 ('Results measure the NVIDIA models through Nebius on this synthetic set only.' if live else
                  'DEMO MODE: these numbers measure simple keyword rules and image statistics, NOT NVIDIA model performance. The routing baseline uses the same keyword rule in demo mode, so routing numbers are expected to match; only a live run gives a meaningful routing comparison. Run with live credentials for model results.') +
                 ' Do not read these as real-world performance.'),
        'routing': routing, 'baseline_routing': base_routing, 'duplicates': dup, 'closure': civic, 'closure_by_evidence': by_evidence,
        'human_review': {'human_rate': human_rate, 'auto_rate': 1 - human_rate}, 'coverage_curve': curve,
        'injection': {'n': len(inj), 'changed': changed},
        'latency': {'p50_s': round(statistics.median(lat), 3), 'p95_s': round(sorted(lat)[max(0, int(len(lat) * 0.95) - 1)], 3),
                    'closure_p50_s': round(statistics.median(c['latency'] for c in cases), 3)},
        'tokens': {'total': toks, 'per_ticket': round(toks / max(1, len(res)), 1)},
        'counts': {'reports': len(use), 'closure_cases': len(cases)},
    }
    out = ROOT / 'eval' / 'results' / 'metrics.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2), encoding='utf-8')
    print(json.dumps({k: metrics[k] for k in ('routing', 'baseline_routing', 'duplicates', 'human_review', 'injection', 'latency')}, indent=2, default=str))
    print('closure (CivicClosure):', {k: (round(v, 3) if isinstance(v, float) else v) for k, v in civic.items() if k != 'baseline'})
    print('closure (trust-resolved baseline):', {k: (round(v, 3) if isinstance(v, float) else v) for k, v in base.items()})
    print('by evidence kind:', by_evidence)
    print('wrote', out)


if __name__ == '__main__':
    main()
