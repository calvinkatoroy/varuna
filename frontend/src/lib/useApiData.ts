import { useCallback, useEffect, useRef, useState, type SetStateAction } from 'react'
import { cacheGet, cacheSet, fetchShared, subscribe } from './swr'

// GET-on-mount with a real failure path (api.ts already toasts, but a page stuck on "Loading..." needs a
// retry). With a `key` the data is cached module-wide (lib/swr.ts): the next visit renders the last answer at
// once and revalidates in the background, and every screen reading the same key follows the newest answer.
// A failed background refresh keeps the data on screen; `error` is set only when there is nothing to show.
// `fresh` turns true once a fetch has finished since mount (use it before declaring something "not found").
// `setData` exists for local optimistic patches (mark fixed, change verdict) and writes through to the cache.
export function useApiData<T>(fetcher: () => Promise<T>, key?: string) {
  const [data, setDataState] = useState<T | null>(() => (key ? cacheGet<T>(key) ?? null : null))
  const [error, setError] = useState<string | null>(null)
  const [fresh, setFresh] = useState(false)
  const latest = useRef<T | null>(data)

  const apply = (next: T | null) => { latest.current = next; setDataState(next) }

  const setData = useCallback((v: SetStateAction<T | null>) => {
    const next = typeof v === 'function' ? (v as (p: T | null) => T | null)(latest.current) : v
    apply(next)
    if (key && next !== null) cacheSet(key, next)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const reload = useCallback(() => {
    setError(null)
    const run = key ? fetchShared(key, fetcher) : fetcher()
    run
      .then((d) => { apply(d); setFresh(true) })
      .catch((e) => { setFresh(true); if (latest.current === null) setError(e?.message || 'Something went wrong.') })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => { reload() }, [reload])
  useEffect(() => {
    if (!key) return
    return subscribe(key, () => { const v = cacheGet<T>(key); if (v !== undefined) apply(v) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { data, error, fresh, reload, setData }
}
