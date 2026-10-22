// Browser-side identity. The workspace id gives each visitor a private sandbox; the role is a DEMO switch.
const uid = () => (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '').slice(0, 20) : String(Date.now()) + Math.random().toString(36).slice(2, 8))

function stored(key, make) {
  let v = localStorage.getItem(key)
  if (!v) { v = make(); localStorage.setItem(key, v) }
  return v
}

export const getWorkspace = () => stored('cc_workspace', () => 'ws-' + uid())
export const getReporterId = () => stored('cc_reporter', () => 'rep-' + uid())
export const getRole = () => localStorage.getItem('cc_role') || 'reporter'
export const setRole = (r) => localStorage.setItem('cc_role', r)
export const newWorkspace = () => { localStorage.setItem('cc_workspace', 'ws-' + uid()); return getWorkspace() }
