import { when } from '../services/format'
import { STATE_META } from '../services/format'

const LABELS = {
  CREATED: 'Report received', INTAKE: 'Report read and structured', ROUTED: 'Department chosen',
  DUPLICATE_CHECK: 'Checked for duplicates', CORROBORATED: 'Another report of the same problem added',
  INFO_PROVIDED: 'Reporter added the location', GATE_RESULT: 'Fix claim checked', ESCALATED: 'Deadline passed: escalated',
  HUMAN_DECISION: 'Human reviewer decided', HUMAN_REVIEW_REQUESTED: 'Sent to a human reviewer',
  REPORTER_CONFIRMATION: 'Reporter responded', AWAITING_CONFIRMATION: 'Waiting for the reporter to confirm',
  INJECTION_FLAG: 'Report text looked like an instruction (ignored)', NOTE: 'Note',
}

function detail(e) {
  const p = e.payload
  if (p == null) return 'Details deleted at the reporter\'s request.'
  switch (e.type) {
    case 'STATE_CHANGED': return (STATE_META[p.from]?.label || p.from) + ' to ' + (STATE_META[p.to]?.label || p.to) + (p.reason ? ' (' + p.reason + ')' : '')
    case 'INTAKE': return p.result ? p.result.issue_type + ', ' + p.result.urgency + ' urgency, confidence ' + Math.round((p.result.confidence ?? 0) * 100) + '%' : ''
    case 'ROUTED': return p.result ? (p.result.department || 'no department') + ': ' + p.result.rationale : ''
    case 'DUPLICATE_CHECK': return p.result ? p.result.reason : ''
    case 'CORROBORATED': return 'Report count is now ' + p.report_count + (p.urgency_raised ? '; urgency raised' : '')
    case 'GATE_RESULT': return 'Verdict: ' + p.verdict
    case 'ESCALATED': return 'Level ' + p.level + ' to the ' + p.notify + (p.simulated ? ' (simulated by the demo clock)' : p.sample_data ? ' (sample data)' : '')
    case 'HUMAN_DECISION': return p.decision + (p.reason ? ': ' + p.reason : '')
    case 'REPORTER_CONFIRMATION': return p.fixed ? 'Says it is fixed' : 'Says it is not fixed'
    case 'AWAITING_CONFIRMATION': return p.reason
    case 'INJECTION_FLAG': return p.note
    case 'NOTE': return p.text
    default: return p.note || ''
  }
}

const dot = { STATE_CHANGED: 'bg-electric', GATE_RESULT: 'bg-violet-500', ESCALATED: 'bg-verdict-bad', HUMAN_DECISION: 'bg-verdict-warn' }

export default function Timeline({ events }) {
  return (
    <ol className="relative border-l-2 border-navy-900/10 ml-2 space-y-4">
      {events.map((e) => (
        <li key={e.seq} className="pl-5 relative">
          <span className={'absolute -left-[7px] top-1.5 h-3 w-3 rounded-full ring-4 ring-white ' + (dot[e.type] || 'bg-navy-900/30')} />
          <p className="text-sm font-semibold">{LABELS[e.type] || e.type}</p>
          <p className="text-sm text-navy-800/80 break-words">{detail(e)}</p>
          <p className="text-xs text-navy-800/75 mt-0.5">{when(e.ts)} by {e.actor}</p>
        </li>
      ))}
    </ol>
  )
}
