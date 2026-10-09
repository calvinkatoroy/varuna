// lib/useFindingsUrl.ts
import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

// The URL is the state of the findings page: ?target=<task id>&finding=<finding id>. Both are written with
// `replace`, so expanding rows never adds history entries (Back leaves the page, as people expect).
export function useFindingsUrl() {
  const [sp, setSp] = useSearchParams()
  const set = useCallback((next: { target?: string | null; finding?: string | null }) => {
    setSp((prev) => {
      const n = new URLSearchParams(prev)
      for (const [k, v] of Object.entries(next)) { if (v) n.set(k, v); else n.delete(k) }
      return n
    }, { replace: true })
  }, [setSp])
  return { target: sp.get('target'), finding: sp.get('finding'), set }
}
