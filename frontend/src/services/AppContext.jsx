import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from './api'
import { getRole, getWorkspace, setRole as saveRole } from './session'

const Ctx = createContext(null)
export const useApp = () => useContext(Ctx)

export function AppProvider({ children }) {
  const [config, setConfig] = useState(null)
  const [configError, setConfigError] = useState('')
  const [role, setRoleState] = useState(getRole())
  const [workspace] = useState(getWorkspace())

  const load = useCallback(() => {
    api.config().then((c) => { setConfig(c); setConfigError('') }).catch((e) => setConfigError(e.message || 'Cannot reach the server'))
  }, [])
  useEffect(() => { load() }, [load])
  // A free host can take about a minute to wake up: keep retrying quietly instead of asking the visitor to refresh.
  useEffect(() => {
    if (!configError) return undefined
    const t = setTimeout(load, 8000)
    return () => clearTimeout(t)
  }, [configError, load])

  const setRole = (r) => { saveRole(r); setRoleState(r) }
  return <Ctx.Provider value={{ config, configError, role, setRole, workspace, reload: load }}>{children}</Ctx.Provider>
}
