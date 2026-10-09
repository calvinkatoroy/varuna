import { useCallback, useEffect, useRef, useState } from 'react'
import { cacheGet, fetchShared, subscribe } from './swr'

// GET-on-mount with a real failure path (api.ts already toasts, but a page stuck on "Loading..." needs a
// retry). With a `key` the data is cached module-wide (lib/swr.ts): the next visit renders the last answer at
// once and revalidates in the background, and every screen reading the same key follows the newest answer.
// A failed background refresh keeps the data on screen; `error` is set only when there is nothing to show.
// `fresh` turns true once a fetch has finished since mount (use it before declaring something "not found").
export function useApiData<T>(fetcher: () => Promise<T>, key?: string) {
  const [data, setData] = useState<T | null>(() => (key ? cacheGet<T>(key) ?? null : null))
  const [error, setError] = useState<string | null>(null)
  const [fresh, setFresh] = useState(false)
  const latest = useRef<T | null>(data)
  const seq = useRef(0)   // newest request of this hook: an older answer that arrives later is ignored

  const apply = (next: T | null) => { latest.current = next; setData(next) }

  // `fresh`: start a new request even if one is in flight (it may predate a change) and let the newest win.
  const load = useCallback((fresh: boolean) => {
    const mine = ++seq.current
    setError(null)
    const run = key ? fetchShared(key, fetcher, fresh) : fetcher()
    run
      .then((d) => { if (mine === seq.current) { apply(d); setFresh(true) } })
      .catch((e) => { if (mine !== seq.current) return; setFresh(true); if (latest.current === null) setError(e?.message || 'Something went wrong.') })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  const reload = useCallback(() => load(true), [load])

  useEffect(() => { load(false) }, [load])
  useEffect(() => {
    if (!key) return
    return subscribe(key, () => { const v = cacheGet<T>(key); if (v !== undefined) apply(v) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { data, error, fresh, reload }
}
