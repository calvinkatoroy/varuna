// lib/useTargetFindings.ts
import { useCallback, useEffect, useRef, useState } from 'react'
import { cacheGet, cacheSet, subscribe } from './swr'
import { findingsApi, mergeRows, rowsKey, type FindingsPage, type Plane, type RowsState } from './findings'

// The rows of ONE open target (and severity filter). They live in the swr cache, so closing and re-opening a
// target, or leaving the page and coming back, shows them at once; on every open they are refreshed with a
// single request (`upto` = the last loaded row returns everything loaded so far). A deep link asks for its own
// row the same way. If that row is gone or hidden by the filter, page one is shown and `focusLost` is set.
export function useTargetFindings(plane: Plane, taskId: string, severity: string | null, focusId: string | null) {
  const key = rowsKey(plane, taskId, severity)
  const [state, setState] = useState<RowsState | null>(() => cacheGet<RowsState>(key) ?? null)
  const [error, setError] = useState<string | null>(null)
  const [gone, setGone] = useState(false)
  const [focusLost, setFocusLost] = useState(false)
  const [busy, setBusy] = useState(false)
  const [tick, setTick] = useState(0)
  const deepLink = useRef(focusId)   // honoured on the first successful load only
  const used = useRef(false)

  useEffect(() => subscribe(key, () => { const s = cacheGet<RowsState>(key); if (s) setState(s) }), [key])

  useEffect(() => {
    let live = true
    const cached = cacheGet<RowsState>(key)
    const focus = used.current ? null : deepLink.current
    setState(cached ?? null); setError(null); setGone(false); setFocusLost(false)
    const fail = (e: any) => { if (live) setError(e?.message || 'Could not load the findings.') }
    const apply = (p: FindingsPage) => {
      if (!live) return
      used.current = true
      const s: RowsState = { items: p.items, next: p.next_cursor, total: p.total }
      cacheSet(key, s)
      setState(s)
    }
    const api = findingsApi(plane)
    const anchor = focus && !cached?.items.some((f) => f.id === focus) ? focus : cached?.items[cached.items.length - 1]?.id
    api.page(taskId, { severity, upto: anchor }).then(apply).catch((e) => {
      if (!live) return
      if (e?.status !== 404 || !anchor) return fail(e)
      if (anchor === focus) setFocusLost(true)
      api.page(taskId, { severity }).then(apply).catch((e2) => { if (live) { if (e2?.status === 404) setGone(true); else fail(e2) } })
    })
    return () => { live = false }
  }, [plane, taskId, severity, key, tick])

  /** Fetch the next page; resolves to the id of the first new row (to move focus there). */
  const loadMore = useCallback(async (): Promise<string | undefined> => {
    const s = cacheGet<RowsState>(key)
    if (!s?.next || busy) return undefined
    setBusy(true)
    try {
      const p = await findingsApi(plane).page(taskId, { cursor: s.next, severity })
      const cur = cacheGet<RowsState>(key) ?? s
      const merged = mergeRows(cur.items, p.items)
      cacheSet(key, { items: merged, next: p.next_cursor, total: p.total })
      return merged[cur.items.length]?.id
    } catch (e: any) {
      setError(e?.message || 'Could not load more findings.')
      return undefined
    } finally {
      setBusy(false)
    }
  }, [plane, taskId, severity, key, busy])

  return { state, error, gone, focusLost, busy, loadMore, retry: () => setTick((n) => n + 1) }
}
