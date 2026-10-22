import { AlertTriangle, Clock, FlaskConical, Link2, RefreshCw, Waypoints } from 'lucide-react'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Link } from 'react-router-dom'
import { Empty, ErrorNote, SampleTag, SlaTimer, Spinner, Stat, StatusBadge } from '../components/ui'
import { api } from '../services/api'
import { useApp } from '../services/AppContext'
import { pct, when } from '../services/format'
import { usePolling } from '../services/hooks'

function Section({ icon: Icon, title, children, hint }) {
  return (
    <section className="card p-5">
      <h2 className="font-display text-xl font-semibold flex items-center gap-2">{Icon && <Icon className="h-5 w-5 text-electric-deep" aria-hidden />}{title}</h2>
      {hint && <p className="text-sm text-navy-800/70 mt-1">{hint}</p>}
      <div className="mt-4">{children}</div>
    </section>
  )
}

function HumanQueue({ stats, onChange }) {
  const { config } = useApp()
  const [reason, setReason] = useState({})
  const [dept, setDept] = useState({})
  const [error, setError] = useState('')
  const q = stats.human_queue
  async function act(id, body) {
    setError('')
    try { await api.humanDecision(id, body); onChange() } catch (e) { setError(e.message) }
  }
  const rows = [...q.routing.map((t) => ({ t, kind: 'routing' })), ...q.closure.map((t) => ({ t, kind: 'closure' }))]
  if (!rows.length) return <Empty title="Nothing waiting for a human">Unclear reports and closures that need a decision appear here.</Empty>
  return (
    <div className="space-y-3">
      <ErrorNote>{error}</ErrorNote>
      {rows.map(({ t, kind }) => (
        <div key={t.id} className="rounded-xl bg-paper p-4 space-y-2">
          <div className="flex flex-wrap items-center gap-2"><Link to={'/tickets/' + t.id} className="font-display font-semibold underline">#{t.id}</Link>
            <StatusBadge state={t.state} /><span className="chip bg-navy-900/8 text-navy-800">{kind === 'routing' ? 'Needs a department' : 'Needs a closure decision'}</span>{t.synthetic && <SampleTag />}</div>
          <p className="text-sm">{t.summary}</p>
          {kind === 'routing' ? (
            <div className="flex flex-wrap gap-2">
              <select aria-label={'Department for ticket ' + t.id} className="field w-auto" value={dept[t.id] || ''} onChange={(e) => setDept({ ...dept, [t.id]: e.target.value })}>
                <option value="">Choose department</option>{Object.entries(config.departments).map(([k, n]) => <option key={k} value={k}>{n}</option>)}</select>
              <button className="btn-dark" disabled={!dept[t.id]} onClick={() => act(t.id, { decision: 'assign_department', department: dept[t.id], reason: 'Assigned by administrator' })}>Assign</button>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <input aria-label={'Reason for ticket ' + t.id} className="field flex-1 min-w-[12rem]" placeholder="Reason (recorded in the audit log)" value={reason[t.id] || ''} onChange={(e) => setReason({ ...reason, [t.id]: e.target.value })} />
              <button className="btn-dark" onClick={() => act(t.id, { decision: 'approve_closure', reason: reason[t.id] || 'Approved by administrator' })}>Approve closure</button>
              <button className="btn-danger" onClick={() => act(t.id, { decision: 'reject_closure', reason: reason[t.id] || 'Rejected by administrator' })}>Reject</button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function Hotspots() {
  const hs = usePolling(() => api.hotspots(), 15000)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function run() { setBusy(true); setError(''); try { await api.runHotspots(); hs.refresh() } catch (e) { setError(e.message) } finally { setBusy(false) } }
  const d = hs.data
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <button className="btn-dark" onClick={run} disabled={busy}>{busy ? <Spinner label="Analysing" /> : <><RefreshCw className="h-4 w-4" aria-hidden />Analyse recurring problems now</>}</button>
        {d?.source && <span className="text-sm text-navy-800/70">Last result from <strong>{d.source === 'job' ? 'the Nebius Serverless Job' : d.source === 'inline-live' ? 'the reasoning model (in-app)' : 'demo rules (in-app, not AI)'}</strong>{d.created_at ? ', ' + when(d.created_at) : ''}</span>}
      </div>
      <ErrorNote>{error}</ErrorNote>
      {d && d.hotspots.length === 0 && <Empty title="No hotspots yet">Run the analysis. A hotspot needs three or more related open tickets.</Empty>}
      {d?.hotspots.map((h, i) => (
        <article key={i} className="rounded-xl border border-navy-900/10 p-4">
          <div className="flex flex-wrap items-center gap-2"><h3 className="font-display font-semibold capitalize">{(h.issue_type || '').replace('_', ' ')}: {h.ticket_ids?.length || 0} related tickets</h3>
            {h.priority && <span className="chip bg-verdict-warnbg text-verdict-warn">{h.priority} priority</span>}{h.model && <span className="chip bg-navy-900/8 text-navy-800">{h.model}</span>}</div>
          {h.error ? <p className="text-sm text-verdict-bad mt-2">{h.error}</p> : <>
            <p className="text-sm mt-2"><strong>Likely root cause:</strong> {h.root_cause_hypothesis}</p>
            <p className="text-sm mt-1"><strong>Consolidated work order:</strong> {h.consolidated_work_order}</p>
            <p className="text-xs mt-2 text-navy-800/70">Tickets: {h.ticket_ids.map((id) => <Link key={id} to={'/tickets/' + id} className="underline mr-2">#{id}</Link>)}</p></>}
        </article>
      ))}
    </div>
  )
}

function Deadlines() {
  const list = usePolling(() => api.tickets({}), 5000)
  const rows = (list.data?.tickets || []).filter((t) => t.sla.seconds_remaining != null).sort((a, b) => a.sla.seconds_remaining - b.sla.seconds_remaining).slice(0, 5)
  if (!rows.length) return null
  return (
    <div className="mt-4">
      <h3 className="font-display font-semibold text-sm mb-2">Closest deadlines</h3>
      <ul className="space-y-1.5">{rows.map((t) => (
        <li key={t.id} className="flex items-center justify-between gap-2 text-sm"><Link to={'/tickets/' + t.id} className="underline truncate">#{t.id} {t.issue_label}</Link><SlaTimer sla={t.sla} state={t.state} /></li>))}</ul>
    </div>
  )
}

function AuditViewer() {
  const list = usePolling(() => api.tickets({}), 15000)
  const [id, setId] = useState('')
  const [audit, setAudit] = useState(null)
  const [error, setError] = useState('')
  async function load(v) {
    setId(v); setAudit(null); setError('')
    if (!v) return
    try { setAudit(await api.audit(v)) } catch (e) { setError(e.message) }
  }
  return (
    <div className="space-y-3">
      <label htmlFor="audit-ticket" className="label">Choose a ticket</label>
      <select id="audit-ticket" className="field max-w-md" value={id} onChange={(e) => load(e.target.value)}>
        <option value="">Select...</option>{(list.data?.tickets || []).map((t) => <option key={t.id} value={t.id}>#{t.id} {t.issue_label}: {t.summary.slice(0, 40)}</option>)}</select>
      <ErrorNote>{error}</ErrorNote>
      {audit && (<>
        <p className={'rounded-xl px-3 py-2 text-sm font-semibold ' + (audit.chain_ok ? 'bg-verdict-okbg text-verdict-ok' : 'bg-verdict-badbg text-verdict-bad')}>
          {audit.chain_ok ? 'Integrity check passed: ' : 'Integrity check FAILED: '}{audit.message} ({audit.event_count} events)</p>
        <p className="text-xs text-navy-800/75">{audit.note}</p>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-navy-800/75"><th className="py-1 pr-3">#</th><th className="pr-3">Time</th><th className="pr-3">Actor</th><th className="pr-3">Event</th><th>Hash</th></tr></thead>
          <tbody>{audit.events.map((e) => <tr key={e.seq} className="border-t border-navy-900/5"><td className="py-1.5 pr-3 tabular-nums">{e.seq}</td><td className="pr-3 whitespace-nowrap">{when(e.ts)}</td><td className="pr-3">{e.actor}</td><td className="pr-3">{e.type}</td><td className="font-mono text-xs">{e.hash}</td></tr>)}</tbody></table></div>
      </>)}
    </div>
  )
}

function Evaluation() {
  const m = usePolling(() => api.metrics(), 60000).data
  if (!m) return <Spinner label="Loading" />
  if (!m.available) return <Empty title="No evaluation results yet">{m.message}</Empty>
  const c = m.closure, b = m.closure?.baseline     // run_eval.py writes CivicClosure's numbers directly under `closure`, the baseline under closure.baseline
  const compare = [
    { name: 'Fake closures accepted', baseline: b?.false_accept_rate, civic: c?.false_accept_rate },
    { name: 'Genuine repairs not accepted', baseline: b?.false_reject_rate, civic: c?.false_reject_rate },
  ].map((r) => ({ ...r, baseline: (r.baseline ?? 0) * 100, civic: (r.civic ?? 0) * 100 }))
  return (
    <div className="space-y-5">
      <div className="rounded-xl bg-verdict-warnbg text-verdict-warn p-3 text-sm"><strong>Read this first.</strong> {m.note} Run on {when(m.generated_at)} in <strong>{m.mode}</strong> mode.</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label="Fake closures accepted" value={pct(c?.false_accept_rate)} hint={'baseline trusting claims: ' + pct(b?.false_accept_rate)} />
        <Stat label="Genuine repairs accepted" value={pct(1 - (c?.false_reject_rate ?? 0))} hint={'n = ' + c?.n_genuine + ' genuine, ' + c?.n_fake + ' fake'} />
        <Stat label="Routing accuracy" value={pct(m.routing?.accuracy)} hint={'macro-F1 ' + (m.routing?.macro_f1?.toFixed(2) ?? 'n/a') + ', n = ' + m.routing?.n} />
        <Stat label="Duplicate detection" value={pct(m.duplicates?.f1)} hint={'precision ' + pct(m.duplicates?.precision) + ', recall ' + pct(m.duplicates?.recall)} />
        <Stat label="Sent to a human" value={pct(m.human_review?.human_rate)} hint="of all test reports" />
        <Stat label="Injection reports that changed routing" value={m.injection ? m.injection.changed + ' of ' + m.injection.n : 'n/a'} />
        <Stat label="Median / p95 latency per report" value={m.latency ? m.latency.p50_s + 's / ' + m.latency.p95_s + 's' : 'n/a'} />
        <Stat label="Tokens per report" value={m.tokens?.per_ticket ?? 'n/a'} hint={m.mode === 'demo' ? 'no tokens used in demo mode' : ''} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div><h3 className="font-display font-semibold mb-2">Closure safety: baseline vs CivicClosure (%)</h3>
          <div className="h-60"><ResponsiveContainer><BarChart data={compare}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" tick={{ fontSize: 12 }} /><YAxis domain={[0, 100]} unit="%" /><Tooltip formatter={(v) => v.toFixed(0) + '%'} /><Legend />
            <Bar dataKey="baseline" name="Trust 'resolved'" fill="#9AA7C8" radius={[6, 6, 0, 0]} /><Bar dataKey="civic" name="CivicClosure" fill="#2F6BFF" radius={[6, 6, 0, 0]} /></BarChart></ResponsiveContainer></div></div>
        <div><h3 className="font-display font-semibold mb-2">Automation vs accuracy (routing)</h3>
          <div className="h-60"><ResponsiveContainer><LineChart data={(m.coverage_curve || []).map((p) => ({ coverage: p.coverage * 100, accuracy: p.accuracy * 100 }))}><CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="coverage" unit="%" label={{ value: 'Share of reports handled automatically', position: 'insideBottom', offset: -2, fontSize: 12 }} height={50} /><YAxis domain={[0, 100]} unit="%" /><Tooltip formatter={(v) => v.toFixed(0) + '%'} />
            <Line type="monotone" dataKey="accuracy" name="Accuracy" stroke="#2F6BFF" strokeWidth={2.5} dot={false} /></LineChart></ResponsiveContainer></div></div>
      </div>
    </div>
  )
}

export default function Admin() {
  const st = usePolling(() => api.stats(), 5000)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const s = st.data

  async function clock(fn) { setBusy(true); setError(''); try { await fn(); st.refresh() } catch (e) { setError(e.message) } finally { setBusy(false) } }

  if (st.loading) return <Spinner label="Loading dashboard" />
  if (!s) return <ErrorNote>{st.error || 'Could not load statistics.'}</ErrorNote>
  const deptData = s.departments.map((d) => ({ name: d.name.replace(' Maintenance', '').replace(' and Water', '').replace(' and ', ' & '), Open: d.open, 'Verified closed': d.verified_closed, Overdue: d.overdue, Reopened: d.reopened }))
  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div><h1 className="font-display text-3xl font-semibold">Administration</h1><p className="mt-1 text-navy-800/75">Everything the AI decided, and everything it was not allowed to decide.</p></div>
        <button className="btn-ghost" onClick={() => clock(() => api.resetWorkspace())} disabled={busy}><RefreshCw className="h-4 w-4" aria-hidden />Reset demo workspace</button>
      </header>
      <ErrorNote>{error}</ErrorNote>
      {s.sample_data_included && <p className="rounded-xl bg-navy-900/6 px-4 py-2.5 text-sm">This workspace includes <strong>synthetic sample tickets</strong> so the dashboard is not empty. They are labelled “Sample data” and are not real complaints.</p>}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <Stat label="Total complaints" value={s.total} /><Stat label="Pending" value={s.pending} /><Stat label="Verified resolutions" value={s.verified_closed} />
        <Stat label="Reopened" value={s.reopened} /><Stat label="Needs evidence" value={s.needs_evidence} /><Stat label="Overdue now" value={s.overdue_now} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1.4fr_1fr] gap-6">
        <Section title="Department performance">
          <div className="h-64"><ResponsiveContainer><BarChart data={deptData}><CartesianGrid strokeDasharray="3 3" vertical={false} /><XAxis dataKey="name" interval={0} tick={{ fontSize: 11 }} /><YAxis allowDecimals={false} /><Tooltip /><Legend />
            <Bar dataKey="Open" fill="#2F6BFF" radius={[4, 4, 0, 0]} /><Bar dataKey="Verified closed" fill="#13A67A" radius={[4, 4, 0, 0]} /><Bar dataKey="Overdue" fill="#D63A4D" radius={[4, 4, 0, 0]} /><Bar dataKey="Reopened" fill="#B7791F" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
        </Section>
        <Section icon={Clock} title="SLA and escalations">
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-navy-800/75">Real escalations</dt><dd className="font-display text-2xl font-semibold">{s.escalations_real}</dd></div>
            <div><dt className="text-navy-800/75">Simulated or sample</dt><dd className="font-display text-2xl font-semibold">{s.escalations_simulated}</dd></div></dl>
          <div className="mt-4 rounded-xl border-2 border-dashed border-verdict-warn/50 bg-verdict-warnbg/50 p-3">
            <p className="text-sm font-semibold text-verdict-warn flex items-center gap-1.5"><AlertTriangle className="h-4 w-4" aria-hidden />DEMO CLOCK (simulated time)</p>
            <p className="text-xs mt-1">Moves only when deadlines are evaluated. Real timestamps are not changed, and escalations it causes are excluded from real performance. Currently +{s.demo_clock_offset_hours} h.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <button className="btn-dark" disabled={busy} onClick={() => clock(() => api.advanceClock(24))}>+24 hours</button>
              <button className="btn-dark" disabled={busy} onClick={() => clock(() => api.advanceClock(72))}>+72 hours</button>
              <button className="btn-ghost" disabled={busy || !s.demo_clock_offset_hours} onClick={() => clock(() => api.resetClock())}>Reset clock</button></div></div>
          <Deadlines />
        </Section>
      </div>
      <Section title="Human review queue" hint="Cases where the system abstained instead of guessing.">
        <HumanQueue stats={s} onChange={st.refresh} />
      </Section>
      <Section icon={Waypoints} title="Recurring problem hotspots" hint="Related tickets grouped into one root-cause work order. The same analysis runs as a Nebius Serverless Job (see jobs/hotspots).">
        <Hotspots />
      </Section>
      <Section icon={Link2} title="AI decision audit history" hint="Every decision is hash-chained. Edits are detected, but the log is tamper-evident, not tamper-proof.">
        <AuditViewer />
      </Section>
      <Section icon={FlaskConical} title="Evaluation results">
        <Evaluation />
      </Section>
      <Section title="AI usage">
        <p className="text-sm">Mode: <strong>{s.ai.mode === 'live' ? 'Live (NVIDIA models through Nebius Token Factory)' : 'Demo (no model calls)'}</strong>. Model calls in this workspace: {s.ai.calls_in_workspace}.
          Tokens used today (all workspaces): {s.ai.tokens_today_all_workspaces.toLocaleString()} of a {s.ai.daily_token_budget.toLocaleString()} daily budget.</p>
      </Section>
    </div>
  )
}
