import { FlaskConical, Play, ShieldCheck, Upload } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Empty, ErrorNote, GatePanel, SampleTag, SlaTimer, Spinner, StatusBadge, UrgencyBadge } from '../components/ui'
import { api } from '../services/api'
import { useApp } from '../services/AppContext'
import { STATE_META, when } from '../services/format'
import { usePolling } from '../services/hooks'

function ClaimPanel({ ticket, onDone }) {
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [outcome, setOutcome] = useState(null)
  const [samples, setSamples] = useState([])
  const stored = JSON.parse(localStorage.getItem('cc_sample_' + ticket.id) || 'null')

  useEffect(() => { setOutcome(null); setFile(null); setNote(''); setError('') }, [ticket.id])
  useEffect(() => { if (!file) { setPreview(''); return undefined } const u = URL.createObjectURL(file); setPreview(u); return () => URL.revokeObjectURL(u) }, [file])
  useEffect(() => { if (stored) api.samples().then((r) => setSamples(r.samples.filter((s) => s.kind === stored.kind && s.role === 'evidence'))).catch(() => {}) }, [ticket.id]) // eslint-disable-line

  async function loadSample(name) {
    if (!name) return
    try { setFile(new File([await api.sampleBlob(name, stored.seed)], name + '.jpg', { type: 'image/jpeg' })) } catch (e) { setError(e.message) }
  }

  async function claim() {
    setBusy(true); setError(''); setOutcome(null)
    const fd = new FormData()
    fd.append('note', note)
    if (file) fd.append('photo', file)
    try { const r = await api.claimClosure(ticket.id, fd); setOutcome(r); onDone() } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const visual = ticket.visual_closure_check
  return (
    <div className="space-y-4">
      <h3 className="font-display text-lg font-semibold">Claim that this is resolved</h3>
      {visual
        ? <p className="text-sm text-navy-800/80">Upload a new photo taken at the same spot. The system checks it before the ticket can close. Typing “fixed” is not enough.</p>
        : <p className="text-sm text-navy-800/80">This kind of problem cannot be checked from a photo. After you claim it, the reporter is asked to confirm, or an administrator decides.</p>}
      <div className="rounded-xl bg-paper p-3 flex gap-3 items-start">
        {preview ? <img src={preview} alt="Preview of the after-repair photo" className="h-24 w-32 rounded-lg object-cover" /> : <div className="grid h-24 w-32 place-items-center rounded-lg border border-dashed border-navy-900/25 text-xs text-navy-800/75">No photo yet</div>}
        <div className="flex-1 space-y-2">
          <label className="btn-ghost cursor-pointer"><Upload className="h-4 w-4" aria-hidden />{file ? 'Choose a different photo' : 'Upload after-repair photo'}
            <input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" onChange={(e) => setFile(e.target.files?.[0] || null)} /></label>
          {stored && samples.length > 0 && (
            <div>
              <label className="flex items-center gap-1.5 text-xs font-medium" htmlFor="sample-evidence"><FlaskConical className="h-3.5 w-3.5" aria-hidden />Or try sample evidence (synthetic)</label>
              <select id="sample-evidence" className="field mt-1 py-1.5" defaultValue="" onChange={(e) => loadSample(e.target.value)}>
                <option value="">Choose sample evidence</option>{samples.map((s) => <option key={s.name} value={s.name}>{s.label}</option>)}</select>
            </div>)}
        </div>
      </div>
      <div><label htmlFor="note" className="label">Note <span className="font-normal text-navy-800/75">(optional, not trusted by the checks)</span></label>
        <input id="note" className="field" maxLength={300} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Replaced the damaged pipe section" /></div>
      <ErrorNote>{error}</ErrorNote>
      <button className="btn-primary" onClick={claim} disabled={busy || (visual && !file)}>{busy ? <Spinner label="Checking the evidence" /> : <><ShieldCheck className="h-4 w-4" aria-hidden />Claim resolution</>}</button>
      {outcome && <GatePanel verdict={outcome.verdict} checks={outcome.checks} whatToFix={outcome.what_to_fix} />}
    </div>
  )
}

export default function Department() {
  const { config } = useApp()
  const [filters, setFilters] = useState({ department: '', urgency: '', state: '' })
  const [selected, setSelected] = useState(null)
  const [error, setError] = useState('')
  const list = usePolling(() => api.tickets(filters), 5000, [filters.department, filters.urgency, filters.state])
  const detail = usePolling(() => (selected ? api.ticket(selected) : Promise.resolve(null)), 5000, [selected])
  const tickets = list.data?.tickets || []
  const t = detail.data
  const before = t?.images?.find((i) => i.kind === 'report')
  const afters = t?.images?.filter((i) => i.kind === 'after') || []
  const canClaim = t && ['ASSIGNED', 'IN_PROGRESS', 'NEEDS_EVIDENCE', 'REOPENED'].includes(t.state)

  async function start() {
    setError('')
    try { await api.start(t.id); detail.refresh(); list.refresh() } catch (e) { setError(e.message) }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="font-display text-3xl font-semibold">Department queue</h1>
        <p className="mt-1 text-navy-800/75">Complaints assigned to departments. A ticket only closes when the evidence passes the verification gate.</p>
      </header>
      <div className="card p-4 grid grid-cols-1 sm:grid-cols-3 gap-3" role="search" aria-label="Filter complaints">
        <div><label htmlFor="f-dept" className="label">Department</label>
          <select id="f-dept" className="field" value={filters.department} onChange={(e) => setFilters({ ...filters, department: e.target.value })}>
            <option value="">All departments</option>{config && Object.entries(config.departments).map(([k, n]) => <option key={k} value={k}>{n}</option>)}</select></div>
        <div><label htmlFor="f-urg" className="label">Urgency</label>
          <select id="f-urg" className="field" value={filters.urgency} onChange={(e) => setFilters({ ...filters, urgency: e.target.value })}>
            <option value="">Any urgency</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></div>
        <div><label htmlFor="f-state" className="label">Status</label>
          <select id="f-state" className="field" value={filters.state} onChange={(e) => setFilters({ ...filters, state: e.target.value })}>
            <option value="">Any status</option>{Object.entries(STATE_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}</select></div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.15fr] gap-6 items-start">
        <section className="card p-2" aria-label="Complaints">
          {list.loading ? <div className="p-4"><Spinner label="Loading complaints" /></div> : tickets.length === 0
            ? <div className="p-3"><Empty title="Nothing matches these filters">Try clearing a filter.</Empty></div>
            : <ul className="divide-y divide-navy-900/5">{tickets.map((x) => (
              <li key={x.id}>
                <button onClick={() => setSelected(x.id)} aria-current={selected === x.id} className={'w-full text-left rounded-xl px-3 py-3 hover:bg-paper ' + (selected === x.id ? 'bg-electric/8' : '')}>
                  <div className="flex items-center justify-between gap-2"><span className="font-display font-semibold">#{x.id} {x.issue_label}</span><SlaTimer sla={x.sla} state={x.state} /></div>
                  <p className="text-sm text-navy-800/80 truncate mt-0.5">{x.summary}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5"><StatusBadge state={x.state} /><UrgencyBadge urgency={x.urgency} />
                    <span className="chip bg-navy-900/8 text-navy-800">{x.department_name || 'No department yet'}</span>{x.report_count > 1 && <span className="chip bg-electric/10 text-electric-deep">{x.report_count} reports</span>}{x.synthetic && <SampleTag />}</div>
                </button>
              </li>))}</ul>}
        </section>
        <section className="card p-5 space-y-5" aria-live="polite" aria-label="Complaint details">
          {!selected && <Empty title="Select a complaint">Pick one from the list to see the evidence and claim a resolution.</Empty>}
          {selected && !t && <Spinner label="Loading" />}
          {t && (<>
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div><h2 className="font-display text-xl font-semibold">#{t.id} {t.issue_label}</h2><p className="text-sm text-navy-800/70">{t.location_text || 'Location not given'} · reported {when(t.created_at)}</p></div>
              <Link to={'/tickets/' + t.id} className="btn-ghost">Full ticket</Link>
            </div>
            <p className="text-sm">{t.summary}</p>
            <div className="flex flex-wrap gap-2"><StatusBadge state={t.state} /><UrgencyBadge urgency={t.urgency} /><SlaTimer sla={t.sla} state={t.state} /></div>
            <div className="grid grid-cols-2 gap-3">
              <figure><figcaption className="text-xs font-semibold mb-1">Before repair (report photo)</figcaption>
                {before ? <img src={api.imageUrl(before.id)} alt="Photo attached to the original report" className="w-full h-36 rounded-xl object-cover" /> : <div className="grid h-36 place-items-center rounded-xl border border-dashed border-navy-900/20 text-xs text-navy-800/75">No photo was attached</div>}</figure>
              <figure><figcaption className="text-xs font-semibold mb-1">After repair (latest claim)</figcaption>
                {afters.length ? <img src={api.imageUrl(afters[afters.length - 1].id)} alt="Most recent after-repair photo" className="w-full h-36 rounded-xl object-cover" /> : <div className="grid h-36 place-items-center rounded-xl border border-dashed border-navy-900/20 text-xs text-navy-800/75">Not uploaded yet</div>}</figure>
            </div>
            <ErrorNote>{error}</ErrorNote>
            {t.state === 'ASSIGNED' && <button className="btn-dark" onClick={start}><Play className="h-4 w-4" aria-hidden />Start work</button>}
            {canClaim && <ClaimPanel ticket={t} onDone={() => { detail.refresh(); list.refresh() }} />}
            {!canClaim && <p className="text-sm rounded-xl bg-paper p-3">{t.state === 'VERIFIED_CLOSED' ? 'This ticket is verified closed.' : t.state === 'CLOSURE_CLAIMED' ? 'Waiting for the reporter or an administrator to confirm this fix.' : 'No action is available in this state (' + STATE_META[t.state]?.label + ').'}</p>}
          </>)}
        </section>
      </div>
    </div>
  )
}
