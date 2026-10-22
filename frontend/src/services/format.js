export const STATE_META = {
  NEW: { label: 'Received', tone: 'slate' },
  NEEDS_INFO: { label: 'Needs your information', tone: 'warn' },
  TRIAGED: { label: 'Under review', tone: 'blue' },
  ASSIGNED: { label: 'Assigned', tone: 'blue' },
  IN_PROGRESS: { label: 'In progress', tone: 'blue' },
  CLOSURE_CLAIMED: { label: 'Fix claimed, checking', tone: 'violet' },
  NEEDS_EVIDENCE: { label: 'Needs better evidence', tone: 'warn' },
  REOPENED: { label: 'Reopened', tone: 'bad' },
  VERIFIED_CLOSED: { label: 'Verified closed', tone: 'ok' },
}

export const TONES = {
  slate: 'bg-navy-900/8 text-navy-800',
  blue: 'bg-electric/10 text-electric-deep',
  violet: 'bg-violet-100 text-violet-800',
  warn: 'bg-verdict-warnbg text-verdict-warn',
  bad: 'bg-verdict-badbg text-verdict-bad',
  ok: 'bg-verdict-okbg text-verdict-ok',
}

export const VERDICT_META = {
  verified: { label: 'Verified', tone: 'ok', text: 'Enough evidence supports closing this ticket.' },
  needs_evidence: { label: 'Needs evidence', tone: 'warn', text: 'The evidence is missing, unclear or not enough yet.' },
  contradicted: { label: 'Contradicted', tone: 'bad', text: 'The evidence conflicts with the claim that this is fixed.' },
  awaiting_confirmation: { label: 'Awaiting confirmation', tone: 'violet', text: 'This problem cannot be checked from a photo. The reporter must confirm, or an administrator decides.' },
}

export const CHECK_LABELS = {
  not_reused: 'Photo is new, not reused',
  fresh: 'Photo was taken after the report',
  state_ok: 'Photo shows the problem fixed',
  same_place: 'Photo shows the same place',
}

export function duration(seconds) {
  if (seconds == null) return ''
  const abs = Math.abs(seconds)
  const d = Math.floor(abs / 86400), h = Math.floor((abs % 86400) / 3600), m = Math.floor((abs % 3600) / 60)
  const txt = d > 0 ? d + 'd ' + h + 'h' : h > 0 ? h + 'h ' + m + 'm' : m + 'm'
  return txt
}

export const when = (iso) => (iso ? new Date(iso + (iso.endsWith('Z') ? '' : 'Z')).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '')

export const pct = (x) => (x == null ? 'n/a' : Math.round(x * 100) + '%')
