import { useCallback, useEffect, useRef, useState } from 'react'

/** Runs `fn` now and then every `ms` milliseconds ("real-time-style" updates through API polling). */
export function usePolling(fn, ms, deps = []) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const refresh = useCallback(async () => {
    try { setData(await fnRef.current()); setError('') } catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [])

  useEffect(() => {
    setLoading(true)
    refresh()
    const t = setInterval(refresh, ms)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ms, refresh, ...deps])

  return { data, error, loading, refresh }
}
