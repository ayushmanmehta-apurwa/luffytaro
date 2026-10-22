import { AlertTriangle, CheckCircle2, Circle, Loader2, ShieldAlert, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { CHECK_LABELS, STATE_META, TONES, VERDICT_META, duration } from '../services/format'

export function Spinner({ label }) {
  return <span className="inline-flex items-center gap-2 text-sm text-navy-800"><Loader2 className="spin h-4 w-4" aria-hidden />{label}</span>
}

export function StatusBadge({ state }) {
  const m = STATE_META[state] || { label: state, tone: 'slate' }
  return <span className={'chip ' + TONES[m.tone]}>{m.label}</span>
}

export function UrgencyBadge({ urgency }) {
  const tone = urgency === 'high' ? 'bad' : urgency === 'low' ? 'slate' : 'warn'
  return <span className={'chip ' + TONES[tone]}>{urgency} urgency</span>
}

export function SourceTag({ source, model }) {
  if (source === 'live') return <span className="chip bg-electric/10 text-electric-deep" title={model}>NVIDIA model{model ? ': ' + model : ''}</span>
  if (source === 'demo') return <span className="chip bg-verdict-warnbg text-verdict-warn" title="Deterministic rules, not an AI model">Demo rules</span>
  if (source === 'rules') return <span className="chip bg-navy-900/8 text-navy-800">Config rules</span>
  return null
}

export function SampleTag() {
  return <span className="chip bg-navy-900/8 text-navy-800" title="Synthetic sample data, not a real complaint">Sample data</span>
}

export function ConfidenceBar({ value }) {
  const v = Math.max(0, Math.min(1, value || 0))
  const color = v >= 0.75 ? 'bg-verdict-ok' : v >= 0.6 ? 'bg-verdict-warn' : 'bg-verdict-bad'
  return (
    <div className="flex items-center gap-2" title={'AI confidence ' + Math.round(v * 100) + '%'}>
      <div className="h-2 w-24 rounded-full bg-navy-900/10 overflow-hidden"><div className={'h-full ' + color} style={{ width: v * 100 + '%' }} /></div>
      <span className="text-xs tabular-nums text-navy-800">{Math.round(v * 100)}%</span>
    </div>
  )
}

export function SlaTimer({ sla, state }) {
  const [secs, setSecs] = useState(sla?.seconds_remaining)
  useEffect(() => {
    setSecs(sla?.seconds_remaining)
    if (sla?.seconds_remaining == null) return undefined
    const t = setInterval(() => setSecs((s) => (s == null ? s : s - 1)), 1000)
    return () => clearInterval(t)
  }, [sla?.seconds_remaining])
  if (secs == null) return <span className="text-xs text-navy-800/75">{state === 'VERIFIED_CLOSED' ? 'Closed' : 'No deadline yet'}</span>
  const over = secs < 0
  return (
    <span className={'chip tabular-nums ' + (over ? TONES.bad : secs < 7200 ? TONES.warn : TONES.slate)}>
      {over ? 'Overdue by ' + duration(secs) : duration(secs) + ' left'}
    </span>
  )
}

export function ErrorNote({ children }) {
  if (!children) return null
  return <div role="alert" className="flex gap-2 rounded-xl bg-verdict-badbg text-verdict-bad px-3.5 py-2.5 text-sm"><AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" aria-hidden /><span>{children}</span></div>
}

export function Empty({ title, children }) {
  return <div className="rounded-2xl border border-dashed border-navy-900/20 p-8 text-center"><p className="font-display font-semibold text-navy-900">{title}</p><p className="mt-1 text-sm text-navy-800/70">{children}</p></div>
}

export function Stat({ label, value, hint }) {
  return (
    <div className="card p-4">
      <p className="text-sm text-navy-800/70">{label}</p>
      <p className="font-display text-3xl font-semibold mt-1 tabular-nums">{value}</p>
      {hint && <p className="text-xs text-navy-800/75 mt-1">{hint}</p>}
    </div>
  )
}

/** The verification ledger: one row per evidence check, then the verdict. This is the product's key moment. */
export function GatePanel({ verdict, checks, whatToFix }) {
  const v = VERDICT_META[verdict]
  const tones = { ok: 'border-verdict-ok bg-verdict-okbg text-verdict-ok', warn: 'border-verdict-warn bg-verdict-warnbg text-verdict-warn',
                  bad: 'border-verdict-bad bg-verdict-badbg text-verdict-bad', violet: 'border-violet-500 bg-violet-100 text-violet-800' }
  return (
    <section aria-label="Verification result" className="rounded-2xl border border-navy-900/10 bg-white overflow-hidden">
      <ul className="divide-y divide-navy-900/8">
        {(checks || []).map((c) => (
          <li key={c.name} className="flex gap-3 px-4 py-3">
            {c.passed ? <CheckCircle2 className="h-5 w-5 text-verdict-ok shrink-0 mt-0.5" aria-label="passed" />
              : c.hard ? <XCircle className="h-5 w-5 text-verdict-bad shrink-0 mt-0.5" aria-label="failed" />
                : <Circle className="h-5 w-5 text-verdict-warn shrink-0 mt-0.5" aria-label="not enough evidence" />}
            <div className="min-w-0">
              <p className="text-sm font-semibold">{CHECK_LABELS[c.name] || c.name}</p>
              <p className="text-sm text-navy-800/75 break-words">{c.detail}</p>
            </div>
          </li>
        ))}
      </ul>
      {v ? (
        <div className={'stamp border-t-4 px-4 py-3 ' + tones[v.tone]}>
          <p className="font-display text-lg font-semibold">{v.label}</p>
          <p className="text-sm">{v.text}</p>
          {whatToFix && whatToFix.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-sm text-navy-900">{whatToFix.map((t) => <li key={t}>{t}</li>)}</ul>
          )}
        </div>
      ) : (
        <div className="border-t-4 border-navy-900/20 px-4 py-3 text-sm text-navy-800"><Spinner label="Checking the evidence" /></div>
      )}
      <p className="px-4 py-2 text-xs text-navy-800/75 bg-paper flex gap-1.5"><ShieldAlert className="h-3.5 w-3.5 shrink-0 mt-0.5" aria-hidden />
        Photo timestamps and visual analysis are evidence checks, not guaranteed proof against manipulation.</p>
    </section>
  )
}
