import { Camera, CheckCircle2, ImagePlus, Loader2, LocateFixed, Send, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Empty, ErrorNote, SampleTag, SlaTimer, SourceTag, Spinner, StatusBadge, UrgencyBadge } from '../components/ui'
import { api } from '../services/api'
import { useApp } from '../services/AppContext'
import { usePolling } from '../services/hooks'

const randomSeed = () => 1 + Math.floor(Math.random() * 99000)

function TicketRow({ t }) {
  return (
    <li>
      <Link to={'/tickets/' + t.id} className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl px-3 py-3 hover:bg-paper">
        <span className="font-display font-semibold tabular-nums">#{t.id}</span>
        <span className="flex-1 min-w-[10rem] text-sm truncate">{t.summary}</span>
        <StatusBadge state={t.state} />
        <SlaTimer sla={t.sla} state={t.state} />
        {t.synthetic && <SampleTag />}
      </Link>
    </li>
  )
}

function Trail({ trail }) {
  return (
    <ol className="space-y-3">
      {trail.map((s) => (
        <li key={s.step} className="rounded-xl bg-paper p-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-display font-semibold">{s.step}</span>
            <SourceTag source={s.source} model={s.model} />
            {s.latency_s != null && s.source === 'live' && <span className="text-xs text-navy-800/75">{s.latency_s}s{s.tokens ? ', ' + s.tokens + ' tokens' : ''}</span>}
          </div>
          <p className="text-sm mt-1"><strong>{s.decision}</strong></p>
          <p className="text-sm text-navy-800/75">{s.why}</p>
          {s.error && <p className="text-xs text-verdict-bad mt-1">AI problem, sent for human handling: {s.error}</p>}
        </li>
      ))}
    </ol>
  )
}

export default function Report() {
  const { config } = useApp()
  const fileRef = useRef(null)
  const [text, setText] = useState('')
  const [building, setBuilding] = useState('')
  const [detail, setDetail] = useState('')
  const [category, setCategory] = useState('')
  const [coords, setCoords] = useState(null)
  const [photo, setPhoto] = useState(null)
  const [preview, setPreview] = useState('')
  const [sample, setSample] = useState(null)       // { kind, seed } when the photo came from a sample button
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [showAll, setShowAll] = useState(false)
  const [info, setInfo] = useState({ building: '', detail: '' })
  const [gpsMsg, setGpsMsg] = useState('')

  const history = usePolling(() => api.tickets(showAll ? {} : { mine: true }), 5000, [showAll])
  const tickets = history.data?.tickets || []

  useEffect(() => { if (!photo) { setPreview(''); return undefined } const u = URL.createObjectURL(photo); setPreview(u); return () => URL.revokeObjectURL(u) }, [photo])

  function pickPhoto(e) {
    const f = e.target.files?.[0]
    setSample(null)
    setPhoto(f || null)
  }

  async function loadSample(kind) {
    setError('')
    try {
      const cat = (await api.samples()).samples.find((s) => s.kind === kind && s.role === 'report')
      const seed = randomSeed()
      const blob = await api.sampleBlob(cat.name, seed)
      setText(cat.text); setBuilding(cat.location); setDetail(cat.detail); setCategory('')
      setPhoto(new File([blob], kind + '.jpg', { type: 'image/jpeg' }))
      setSample({ kind, seed })
    } catch (e) { setError(e.message) }
  }

  function locate() {
    if (!navigator.geolocation) { setGpsMsg('Your browser does not support location.'); return }
    setGpsMsg('Finding your location...')
    navigator.geolocation.getCurrentPosition(
      (p) => { setCoords({ lat: +p.coords.latitude.toFixed(5), lng: +p.coords.longitude.toFixed(5) }); setGpsMsg('') },
      () => setGpsMsg('Could not get your location. You can still choose the place from the list.'),
      { timeout: 8000 })
  }

  async function submit(e) {
    e.preventDefault()
    setError(''); setResult(null); setBusy(true)
    const fd = new FormData()
    fd.append('text', text); fd.append('building', building); fd.append('detail', detail); fd.append('category', category)
    if (coords) { fd.append('lat', coords.lat); fd.append('lng', coords.lng) }
    if (photo) fd.append('photo', photo)
    try {
      const r = await api.createReport(fd)
      setResult(r)
      if (sample && r.ticket_id) localStorage.setItem('cc_sample_' + r.ticket_id, JSON.stringify(sample))
      setText(''); setDetail(''); setPhoto(null); setSample(null); setCoords(null)
      if (fileRef.current) fileRef.current.value = ''
      history.refresh()
    } catch (err) { setError(err.message) } finally { setBusy(false) }
  }

  async function sendInfo(e) {
    e.preventDefault()
    setError('')
    try { const t = await api.provideInfo(result.ticket.id, info); setResult({ ...result, ticket: t, followup: null }); history.refresh() } catch (err) { setError(err.message) }
  }

  const t = result?.ticket
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_1fr] gap-6 items-start">
      <div className="space-y-6">
        <header>
          <h1 className="font-display text-3xl font-semibold">Report a campus problem</h1>
          <p className="mt-1 text-navy-800/75">Describe it in English, Hindi or Hinglish and add a photo. We will tell you who is handling it and when it is due.</p>
        </header>
        <form onSubmit={submit} className="card p-5 space-y-4" aria-busy={busy}>
          <div>
            <label htmlFor="text" className="label">What is the problem?</label>
            <textarea id="text" required minLength={5} maxLength={2000} rows={4} className="field" value={text} onChange={(e) => setText(e.target.value)}
              placeholder="For example: the stair light is not working and it is very dark at night" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="building" className="label">Where on campus?</label>
              <select id="building" className="field" value={building} onChange={(e) => setBuilding(e.target.value)}>
                <option value="">Choose a place (or mention it above)</option>
                {config?.locations.map((l) => <option key={l}>{l}</option>)}
              </select>
            </div>
            <div>
              <label htmlFor="detail" className="label">Floor, room or landmark <span className="font-normal text-navy-800/75">(optional)</span></label>
              <input id="detail" maxLength={200} className="field" value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="2nd floor corridor" />
            </div>
            <div>
              <label htmlFor="category" className="label">Type of problem <span className="font-normal text-navy-800/75">(optional)</span></label>
              <select id="category" className="field" value={category} onChange={(e) => setCategory(e.target.value)}>
                <option value="">Let AI decide</option>
                {config && Object.entries(config.issue_types).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
              </select>
            </div>
            <div>
              <span className="label">GPS location <span className="font-normal text-navy-800/75">(optional)</span></span>
              <button type="button" onClick={locate} className="btn-ghost w-full"><LocateFixed className="h-4 w-4" aria-hidden />{coords ? coords.lat + ', ' + coords.lng : 'Use my location'}</button>
              {gpsMsg && <p className="mt-1 text-xs text-navy-800/70" role="status">{gpsMsg}</p>}
            </div>
          </div>
          <div>
            <span className="label">Photo</span>
            {preview ? (
              <div className="flex items-start gap-3">
                <img src={preview} alt="Preview of the photo you will upload" className="h-28 w-40 rounded-xl object-cover border border-navy-900/10" />
                <button type="button" className="btn-ghost" onClick={() => { setPhoto(null); setSample(null); if (fileRef.current) fileRef.current.value = '' }}><Trash2 className="h-4 w-4" aria-hidden />Remove</button>
              </div>
            ) : (
              <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-navy-900/25 px-4 py-5 hover:bg-paper">
                <ImagePlus className="h-6 w-6 text-electric-deep" aria-hidden />
                <span className="text-sm"><strong>Take or upload a photo</strong><br /><span className="text-navy-800/70">JPEG, PNG or WebP, up to 5 MB. Use the phone camera so the capture time is saved.</span></span>
                <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" onChange={pickPhoto} />
              </label>
            )}
          </div>
          <ErrorNote>{error}</ErrorNote>
          <div className="flex flex-wrap items-center gap-3">
            <button className="btn-primary" disabled={busy || text.trim().length < 5}>{busy ? <Loader2 className="spin h-4 w-4" aria-hidden /> : <Send className="h-4 w-4" aria-hidden />}{busy ? 'AI is reading your report...' : 'Submit complaint'}</button>
            <span className="text-xs text-navy-800/75">Do not include personal details. You can delete your report later.</span>
          </div>
        </form>

        <div className="card p-5">
          <h2 className="font-display text-lg font-semibold flex items-center gap-2"><Camera className="h-5 w-5 text-electric-deep" aria-hidden />Try a sample report</h2>
          <p className="text-sm text-navy-800/70 mt-1">Fills the form with an example and a generated illustration photo, so you can try the whole flow. Samples are synthetic.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {[['broken_light', 'Broken stair light'], ['water_leak', 'Water leak'], ['garbage_overflow', 'Garbage overflow'], ['blocked_path', 'Blocked corridor']].map(([k, l]) =>
              <button key={k} type="button" className="btn-ghost" onClick={() => loadSample(k)}>{l}</button>)}
          </div>
        </div>
      </div>

      <div className="space-y-6">
        {busy && <div className="card p-5"><Spinner label="Reading the report, choosing a department and checking for duplicates" /></div>}
        {t && (
          <section className="card p-5 space-y-4" aria-live="polite">
            <div className="flex items-center gap-2 text-verdict-ok"><CheckCircle2 className="h-5 w-5" aria-hidden /><h2 className="font-display text-xl font-semibold text-navy-900">
              {result.merged_into ? 'Already reported: you were added to ticket #' + t.id : 'Complaint ID #' + t.id}</h2></div>
            {result.merged_into && <p className="text-sm text-navy-800/80">Someone reported the same problem. We merged your report into the existing ticket, which now has {t.report_count} reports.</p>}
            <div className="flex flex-wrap gap-2"><StatusBadge state={t.state} /><UrgencyBadge urgency={t.urgency} /><SlaTimer sla={t.sla} state={t.state} /></div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div><dt className="text-navy-800/75">Problem</dt><dd className="font-semibold">{t.issue_label}</dd></div>
              <div><dt className="text-navy-800/75">Handled by</dt><dd className="font-semibold">{t.department_name || 'A human reviewer will choose'}</dd></div>
            </dl>
            {t.state === 'NEEDS_INFO' && (
              <form onSubmit={sendInfo} className="rounded-xl bg-verdict-warnbg p-4 space-y-3">
                <p className="text-sm font-semibold text-verdict-warn">{result.followup || t.followup_question}</p>
                <select required className="field" aria-label="Campus location" value={info.building} onChange={(e) => setInfo({ ...info, building: e.target.value })}>
                  <option value="">Choose a place</option>{config?.locations.map((l) => <option key={l}>{l}</option>)}</select>
                <input className="field" aria-label="Floor or room" placeholder="Floor, room or landmark (optional)" value={info.detail} onChange={(e) => setInfo({ ...info, detail: e.target.value })} />
                <button className="btn-dark">Send</button>
              </form>
            )}
            <div><h3 className="font-display font-semibold mb-2">What the system decided</h3><Trail trail={result.trail} /></div>
            <Link to={'/tickets/' + t.id} className="btn-ghost w-full">Open full ticket</Link>
          </section>
        )}
        <section className="card p-3">
          <div className="flex items-center justify-between px-3 pt-2 pb-1">
            <h2 className="font-display text-lg font-semibold">{showAll ? 'All tickets in this demo workspace' : 'Your reports'}</h2>
            <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />Include sample tickets</label>
          </div>
          <p className="px-3 text-xs text-navy-800/75">Updates every few seconds.</p>
          {history.loading ? <div className="p-4"><Spinner label="Loading" /></div> : tickets.length === 0
            ? <div className="p-3"><Empty title="No reports yet">Submit one above, or try a sample report.</Empty></div>
            : <ul className="divide-y divide-navy-900/5 mt-2">{tickets.map((x) => <TicketRow key={x.id} t={x} />)}</ul>}
        </section>
      </div>
    </div>
  )
}
