import { useEffect, useState } from 'react'
import { ACTION_LABEL, auditApi, trailDetail, type TrailRow } from '@/lib/audit'
import { when } from '@/lib/format'

export function Trail({ tid, rev }: { tid: string; rev: number }) {
  const [rows, setRows] = useState<TrailRow[] | null>(null)
  useEffect(() => {
    let live = true
    auditApi.trail(tid).then((r) => { if (live) setRows(r) }).catch(() => { if (live) setRows([]) })
    return () => { live = false }
  }, [tid, rev])
  return (
    <details className="rounded-bento-lg border border-rule bg-card">
      <summary className="flex min-h-[44px] cursor-pointer items-center px-5 text-[13px] font-semibold text-ink">Audit trail {rows ? `(${rows.length})` : ''}</summary>
      <ol className="space-y-2 border-t border-rule p-5">
        {(rows ?? []).map((r) => (
          <li key={r.id} className="text-[13px]">
            <span className="font-semibold text-ink">{ACTION_LABEL[r.action] ?? r.action}</span>
            <span className="text-ink-muted"> · {r.actor} · {when(r.at)}</span>
            {trailDetail(r) && <div className="break-words text-ink-muted">{trailDetail(r)}</div>}
          </li>
        ))}
        {rows && rows.length === 0 && <li className="text-[13px] text-ink-muted">Nothing has been changed yet.</li>}
      </ol>
    </details>
  )
}
