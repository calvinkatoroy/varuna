// lib/useFindingDetail.ts
import { useEffect, useState } from 'react'
import { cacheGet, fetchShared } from './swr'
import { findingsApi, type FindingFull, type Plane } from './findings'

// The full record (evidence, remediation) of the row whose drawer is open. List rows are summaries on purpose.
export function useFindingDetail(plane: Plane, id: string | null) {
  const [detail, setDetail] = useState<FindingFull | null>(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    setFailed(false)
    if (!id) { setDetail(null); return }
    const key = `${plane}:/api/findings/id/${id}`
    setDetail(cacheGet<FindingFull>(key) ?? null)
    let live = true
    fetchShared(key, () => findingsApi(plane).one(id))
      .then((d) => { if (live) setDetail(d) })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [plane, id])
  return { detail, failed }
}
