import { ArrowRight, Copy, Eye, FileSearch, Hourglass, Link2, ShieldCheck, Sparkles, Waypoints } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Brand, ModeBanner } from '../components/Layout'
import { GatePanel } from '../components/ui'
import { useApp } from '../services/AppContext'

// Illustrative scenarios for the walkthrough. This is a scripted explanation of the gate's logic, NOT a live model call.
const SCENARIOS = [
  { id: 'genuine', label: 'Genuine repair photo', verdict: 'verified', checks: [
    { name: 'not_reused', passed: true, hard: true, detail: 'A new photo that has not been used before.' },
    { name: 'fresh', passed: true, hard: true, detail: 'Taken 1 minute ago, after the report.' },
    { name: 'state_ok', passed: true, hard: true, detail: 'The staircase light is on.' },
    { name: 'same_place', passed: true, hard: true, detail: 'Same staircase and viewpoint as the report.' }] },
  { id: 'reused', label: 'Original photo sent again', verdict: 'contradicted', checks: [
    { name: 'not_reused', passed: false, hard: true, detail: 'Identical to the photo attached to the report.' },
    { name: 'fresh', passed: false, hard: true, detail: 'Capture time is before the report was made.' },
    { name: 'state_ok', passed: false, hard: true, detail: 'The light is still off.' },
    { name: 'same_place', passed: true, hard: true, detail: 'Same staircase.' }] },
  { id: 'elsewhere', label: 'Photo from another corridor', verdict: 'contradicted', checks: [
    { name: 'not_reused', passed: true, hard: true, detail: 'A new photo.' },
    { name: 'fresh', passed: true, hard: true, detail: 'Taken 2 minutes ago.' },
    { name: 'state_ok', passed: true, hard: true, detail: 'A light is on in this photo.' },
    { name: 'same_place', passed: false, hard: true, detail: 'This is a different corridor from the report.' }] },
  { id: 'screenshot', label: 'Screenshot with no capture time', verdict: 'needs_evidence', checks: [
    { name: 'not_reused', passed: true, hard: true, detail: 'A new image.' },
    { name: 'fresh', passed: false, hard: false, detail: 'No capture time in the file. Retake it with the phone camera.' },
    { name: 'state_ok', passed: false, hard: false, detail: 'The light looks on, but the image is too unclear to be sure.' },
    { name: 'same_place', passed: true, hard: true, detail: 'Looks like the same staircase.' }] },
]

function ClaimDemo() {
  const [picked, setPicked] = useState(null)
  const [shown, setShown] = useState(0)
  const timer = useRef(null)
  const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  useEffect(() => () => clearInterval(timer.current), [])
  function run(s) {
    clearInterval(timer.current)
    setPicked(s)
    if (reduce) { setShown(s.checks.length); return }
    setShown(0)
    let n = 0
    timer.current = setInterval(() => { n += 1; setShown(n); if (n >= s.checks.length) clearInterval(timer.current) }, 520)
  }
  const done = picked && shown >= picked.checks.length
  return (
    <div className="rounded-3xl bg-white p-5 sm:p-6 text-navy-900 shadow-2xl">
      <p className="text-sm text-navy-800/70">Stair light, Hostel B</p>
      <p className="font-display text-xl font-semibold mt-0.5">Electrical says: “Resolved.” Do we believe it?</p>
      <p className="text-sm mt-3 mb-2 font-medium">Choose the evidence they upload:</p>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Evidence options">
        {SCENARIOS.map((s) => (
          <button key={s.id} onClick={() => run(s)} aria-pressed={picked?.id === s.id}
            className={'rounded-full px-3.5 py-1.5 text-sm font-semibold border transition-colors ' + (picked?.id === s.id ? 'bg-electric text-white border-electric' : 'border-navy-900/20 hover:bg-paper')}>{s.label}</button>
        ))}
      </div>
      <div className="mt-4 min-h-[250px]" aria-live="polite">
        {picked ? <GatePanel verdict={done ? picked.verdict : null} checks={picked.checks.slice(0, shown)} />
          : <div className="rounded-2xl border border-dashed border-navy-900/20 p-6 text-sm text-navy-800/70">Pick an option to see how the verification gate decides.</div>}
      </div>
      <p className="mt-3 text-xs text-navy-800/75">Illustrative walkthrough of the gate’s logic. It does not call an AI model.</p>
    </div>
  )
}

const STEPS = [
  ['A student reports a problem', 'Text, a photo and a campus location. Hindi, English or Hinglish.'],
  ['The AI structures it', 'Issue type, urgency and place are extracted and validated before anything else happens.'],
  ['It reaches the right team', 'Rules map known issues to departments. Unsure cases go to a human, not a guess.'],
  ['The department claims a fix', 'They upload an after photo. Nobody can simply click “done”.'],
  ['The evidence is checked', 'Reused photos, wrong places and missing proof are caught. Only a pass closes the ticket.'],
]

const FEATURES = [
  [Copy, 'One problem, one ticket', 'Ten people reporting the same broken light become one ticket with a report count, not ten.'],
  [Eye, 'Closure needs proof', 'Photo reuse, capture time, the fixed state and the location are all checked before a ticket closes.'],
  [Hourglass, 'Deadlines that escalate', 'Each department has a service deadline. Overdue tickets escalate to a supervisor automatically.'],
  [Link2, 'A history nobody can quietly edit', 'Every decision is written to a hash-chained log. Edits are detected.'],
  [Waypoints, 'Finds the real cause', 'Fourteen tickets about one hostel’s water pressure become one root-cause work order.'],
  [ShieldCheck, 'Private by design', 'Reporters can delete their photos and text. Report text is treated as data, never as instructions.'],
]

export default function Landing() {
  const { setRole } = useApp()
  const nav = useNavigate()
  return (
    <div className="min-h-full bg-navy-950 text-white">
      <ModeBanner />
      <header className="max-w-6xl mx-auto flex items-center justify-between px-4 sm:px-6 py-5">
        <Brand />
        <nav className="flex items-center gap-2 sm:gap-5 text-sm">
          <a href="#how" className="hidden sm:inline text-white/75 hover:text-white">How it works</a>
          <a href="#features" className="hidden sm:inline text-white/75 hover:text-white">Features</a>
          <button onClick={() => { setRole('admin'); nav('/admin') }} className="btn bg-white/10 text-white hover:bg-white/20">Explore dashboard</button>
        </nav>
      </header>

      <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-8 pb-16 sm:pt-14 sm:pb-24 grid grid-cols-1 lg:grid-cols-[1.05fr_1fr] gap-10 lg:gap-14 items-center">
        <div>
          <h1 className="font-display font-semibold text-4xl sm:text-5xl lg:text-6xl leading-[1.04]">Report Smarter. Resolve Faster. Verify Every Fix.</h1>
          <p className="mt-6 text-lg text-white/75 max-w-xl">On most campuses a problem gets marked “resolved” and stays broken. CivicClosure checks the evidence before it lets a ticket close.</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <button onClick={() => { setRole('reporter'); nav('/report') }} className="btn-primary px-5 py-3 text-base">Report an Issue <ArrowRight className="h-4 w-4" aria-hidden /></button>
            <button onClick={() => { setRole('admin'); nav('/admin') }} className="btn bg-white/10 text-white hover:bg-white/20 px-5 py-3 text-base">Explore Dashboard</button>
          </div>
          <p className="mt-6 flex items-center gap-2 text-sm text-white/55"><Sparkles className="h-4 w-4" aria-hidden />Built on NVIDIA Nemotron models through Nebius Token Factory. Runs in a clearly labelled demo mode without them.</p>
        </div>
        <ClaimDemo />
      </section>

      <section id="how" className="bg-white text-navy-900">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-16">
          <h2 className="font-display text-3xl font-semibold">How a report becomes a verified fix</h2>
          <ol className="mt-8 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {STEPS.map(([t, d], i) => (
              <li key={t} className="rounded-2xl bg-paper p-5">
                <span className="font-display text-sm font-semibold text-electric-deep">Step {i + 1}</span>
                <p className="mt-2 font-display font-semibold leading-snug">{t}</p>
                <p className="mt-2 text-sm text-navy-800/80">{d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="features" className="max-w-6xl mx-auto px-4 sm:px-6 py-16">
        <h2 className="font-display text-3xl font-semibold">Made for the people who live with the problem</h2>
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8">
          {FEATURES.map(([Icon, t, d]) => (
            <div key={t} className="flex gap-4">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-electric/15 text-electric-soft"><Icon className="h-5 w-5" aria-hidden /></span>
              <div><h3 className="font-display text-lg font-semibold">{t}</h3><p className="mt-1 text-white/70">{d}</p></div>
            </div>
          ))}
        </div>
        <div className="mt-12 rounded-2xl bg-white/6 p-5 text-sm text-white/70 flex gap-3"><FileSearch className="h-5 w-5 shrink-0 text-electric-soft" aria-hidden />
          <p>Photo timestamps and visual analysis are evidence checks, not guaranteed proof against manipulation. The audit log is tamper-evident, not tamper-proof. The role switcher in the app is a demo convenience, not real authentication.</p></div>
      </section>
      <footer className="border-t border-white/10 px-4 py-6 text-center text-sm text-white/50">
        CivicClosure, built for the Nebius × NVIDIA Global AI Hackathon. <Link to="/report" className="underline">Try it</Link>
      </footer>
    </div>
  )
}
