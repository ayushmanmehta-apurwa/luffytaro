import { ArrowLeft, Link2, ThumbsDown, ThumbsUp, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Timeline from '../components/Timeline'
import { ConfidenceBar, ErrorNote, GatePanel, SampleTag, SlaTimer, SourceTag, Spinner, StatusBadge, UrgencyBadge } from '../components/ui'
import { api } from '../services/api'
import { useApp } from '../services/AppContext'
import { when } from '../services/format'
import { usePolling } from '../services/hooks'

function Photo({ img, caption, empty }) {
  return (
    <figure>
      <figcaption className="text-sm font-semibold mb-1">{caption}</figcaption>
      {img ? <>
        <img src={api.imageUrl(img.id)} alt={caption} className="w-full h-48 rounded-xl object-cover border border-navy-900/10" />
        <p className="text-xs text-navy-800/75 mt-1">{img.exif_time ? 'Camera capture time: ' + img.exif_time.replace('T', ' ') : 'No capture time stored in the photo'}</p></>
        : <div className="grid h-48 place-items-center rounded-xl border border-dashed border-navy-900/20 text-sm text-navy-800/75">{empty}</div>}
    </figure>
  )
}

export default function TicketDetail() {
  const { id } = useParams()
  const { role, config } = useApp()
  const tk = usePolling(() => api.ticket(id), 5000, [id])
  const [audit, setAudit] = useState(null)
  const [error, setError] = useState('')
  const [comment, setComment] = useState('')
  const [info, setInfo] = useState({ building: '', detail: '' })
  const [deleted, setDeleted] = useState('')
  const t = tk.data

  async function run(fn) { setError(''); try { await fn(); tk.refresh() } catch (e) { setError(e.message) } }
  if (tk.loading) return <Spinner label="Loading ticket" />
  if (!t) return <div className="space-y-3"><ErrorNote>{tk.error || 'Ticket not found'}</ErrorNote><Link to="/report" className="btn-ghost">Back</Link></div>

  const reports = t.images.filter((i) => i.kind === 'report'), afters = t.images.filter((i) => i.kind === 'after')
  const gate = [...t.events].reverse().find((e) => e.type === 'GATE_RESULT')
  const intake = t.events.find((e) => e.type === 'INTAKE')
  const routed = t.events.find((e) => e.type === 'ROUTED')
  const canConfirm = ['reporter', 'admin'].includes(role) && ['CLOSURE_CLAIMED', 'NEEDS_EVIDENCE', 'VERIFIED_CLOSED'].includes(t.state)

  return (
    <div className="space-y-6">
      <Link to={role === 'reporter' ? '/report' : role === 'department' ? '/department' : '/admin'} className="inline-flex items-center gap-1.5 text-sm font-medium text-electric-deep"><ArrowLeft className="h-4 w-4" aria-hidden />Back</Link>
      <header className="card p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-display text-3xl font-semibold">Complaint #{t.id}</h1><StatusBadge state={t.state} /><UrgencyBadge urgency={t.urgency} />{t.synthetic && <SampleTag />}
          {t.report_count > 1 && <span className="chip bg-electric/10 text-electric-deep">{t.report_count} people reported this</span>}
        </div>
        <p className="mt-3 text-lg">{t.original_text || t.summary}</p>
        <dl className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
          <div><dt className="text-navy-800/75">Problem</dt><dd className="font-semibold">{t.issue_label}</dd></div>
          <div><dt className="text-navy-800/75">Location</dt><dd className="font-semibold">{t.location_text || 'Not given'}</dd></div>
          <div><dt className="text-navy-800/75">Assigned department</dt><dd className="font-semibold">{t.department_name || 'Waiting for a human reviewer'}</dd></div>
          <div><dt className="text-navy-800/75">Deadline</dt><dd><SlaTimer sla={t.sla} state={t.state} /></dd></div>
          <div><dt className="text-navy-800/75">AI confidence</dt><dd><ConfidenceBar value={t.confidence} /></dd></div>
          <div><dt className="text-navy-800/75">Decided by</dt><dd className="flex flex-wrap gap-1.5"><SourceTag source={intake?.payload?.meta?.source || t.ai_source} model={intake?.payload?.meta?.model} /><SourceTag source={routed?.payload?.meta?.source} model={routed?.payload?.meta?.model} /></dd></div>
        </dl>
        {t.state === 'NEEDS_INFO' && ['reporter', 'admin'].includes(role) && (
          <form className="mt-4 rounded-xl bg-verdict-warnbg p-4 space-y-3 max-w-md" onSubmit={(e) => { e.preventDefault(); run(() => api.provideInfo(t.id, info)) }}>
            <p className="text-sm font-semibold text-verdict-warn">{t.followup_question}</p>
            <select required className="field" aria-label="Campus location" value={info.building} onChange={(e) => setInfo({ ...info, building: e.target.value })}><option value="">Choose a place</option>{config?.locations.map((l) => <option key={l}>{l}</option>)}</select>
            <input className="field" aria-label="Floor or room" placeholder="Floor, room or landmark (optional)" value={info.detail} onChange={(e) => setInfo({ ...info, detail: e.target.value })} />
            <button className="btn-dark">Send</button></form>)}
      </header>
      <ErrorNote>{error}</ErrorNote>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <section className="card p-5 space-y-4" aria-label="Evidence">
          <h2 className="font-display text-xl font-semibold">Before and after evidence</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4"><Photo img={reports[0]} caption="Before: photo with the report" empty="No photo was attached" /><Photo img={afters[afters.length - 1]} caption="After: latest repair photo" empty="No repair photo yet" /></div>
          <h3 className="font-display font-semibold pt-2">Resolution verification</h3>
          {gate ? <GatePanel verdict={gate.payload?.verdict} checks={gate.payload?.checks} />
            : <p className="text-sm rounded-xl bg-paper p-3">{t.last_verdict === 'awaiting_confirmation' ? 'This problem cannot be checked from a photo. The reporter confirms the fix, or an administrator decides.' : 'No repair has been claimed yet.'}</p>}
          {canConfirm && (
            <div className="rounded-xl bg-paper p-4 space-y-3">
              <p className="text-sm font-semibold">Reporter confirmation</p>
              <input className="field" aria-label="Comment" maxLength={300} placeholder="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
              <div className="flex flex-wrap gap-2">
                <button className="btn-dark" onClick={() => run(() => api.confirm(t.id, true, comment))}><ThumbsUp className="h-4 w-4" aria-hidden />It is fixed</button>
                <button className="btn-danger" onClick={() => run(() => api.confirm(t.id, false, comment))}><ThumbsDown className="h-4 w-4" aria-hidden />It is not fixed</button></div>
              <p className="text-xs text-navy-800/75">For problems that can be checked in a photo, your confirmation is recorded as evidence but cannot close the ticket by itself.</p>
            </div>)}
        </section>
        <section className="card p-5" aria-label="Timeline">
          <h2 className="font-display text-xl font-semibold mb-4">Complaint timeline</h2>
          <Timeline events={t.events} />
        </section>
      </div>

      <section className="card p-5 space-y-3" aria-label="Audit history">
        <h2 className="font-display text-xl font-semibold flex items-center gap-2"><Link2 className="h-5 w-5 text-electric-deep" aria-hidden />Audit history</h2>
        <p className="text-sm text-navy-800/70">Each event is hashed together with the one before it, so quiet edits are detected. This is tamper-evident, not tamper-proof.</p>
        <div className="flex flex-wrap gap-2">
          <button className="btn-dark" onClick={() => run(async () => setAudit(await api.audit(t.id)))}>Verify audit integrity</button>
          {['reporter', 'admin'].includes(role) && <button className="btn-danger" onClick={() => { if (window.confirm('Delete the photos and text of this report? This cannot be undone.')) run(async () => { const r = await api.deleteData(t.id); setDeleted('Your photos and text were deleted. The audit chain still verifies: ' + r.chain_still_valid + '.') }) }}><Trash2 className="h-4 w-4" aria-hidden />Delete my photos and text</button>}
        </div>
        {deleted && <p role="status" className="text-sm rounded-xl bg-verdict-okbg text-verdict-ok px-3 py-2">{deleted}</p>}
        {audit && <p role="status" className={'rounded-xl px-3 py-2 text-sm font-semibold ' + (audit.chain_ok ? 'bg-verdict-okbg text-verdict-ok' : 'bg-verdict-badbg text-verdict-bad')}>
          {audit.chain_ok ? 'Integrity check passed' : 'Integrity check FAILED'}: {audit.message} ({audit.event_count} events)</p>}
        <p className="text-xs text-navy-800/75">First report received {when(t.created_at)}.</p>
      </section>
    </div>
  )
}
