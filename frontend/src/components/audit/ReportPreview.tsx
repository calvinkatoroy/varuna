import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { ErrorRetry } from '@/components/ErrorRetry'
import { auditApi, groupItems, type ContentView, type PreviewItem } from '@/lib/audit'
import { SEV_CHIP, SEV_LABEL, sevOf } from '@/lib/findings'
import { when } from '@/lib/format'
import { toast } from '@/lib/toast'

function Item({ it }: { it: ReturnType<typeof groupItems>[number] }) {
  switch (it.kind) {
    case 'paragraph': return <p className="break-words text-[13.5px] leading-relaxed text-ink">{it.text}</p>
    case 'list': return <ul className="ml-5 list-disc space-y-1 break-words text-[13.5px] leading-relaxed text-ink">{it.items.map((t, i) => <li key={i}>{t}</li>)}</ul>
    case 'cover': return <p className="text-[13px] text-ink-muted">{it.client} · {it.target}</p>
    case 'counts': return (
      <div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(it.counts).map(([s, n]) => <span key={s} className={`rounded-md px-2 py-1 text-[12px] font-bold ${SEV_CHIP[sevOf(s)]}`}>{SEV_LABEL[sevOf(s)]} {n}</span>)}
        </div>
        <p className="mt-2 text-[13px] text-ink">Overall risk rating: <b>{it.risk}</b></p>
      </div>
    )
    case 'kv': return (
      <dl className="grid grid-cols-[minmax(90px,auto)_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-[13px]">
        {it.rows.map(([k, v]) => <div key={k} className="contents"><dt className="break-words text-ink-muted">{k}</dt><dd className="break-words text-ink">{v}</dd></div>)}
      </dl>
    )
    case 'table': return (
      <div className="overflow-x-auto">
        <table className="w-full min-w-[480px] border-collapse text-left text-[12.5px]">
          <thead><tr>{it.header.map((h) => <th key={h} className="border-b border-rule px-2 py-2 font-semibold text-ink-muted">{h}</th>)}</tr></thead>
          <tbody>{it.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className="border-b border-rule px-2 py-2 align-top text-ink">{j === it.sev_col ? SEV_LABEL[sevOf(String(c))] : String(c)}</td>)}</tr>)}</tbody>
        </table>
      </div>
    )
    case 'finding': return (
      <div className="rounded-input border border-rule bg-panel p-3.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mono text-[12px] text-ink-muted">{it.f._id}</span>
          <span className={`rounded-md px-2 py-0.5 text-[12px] font-bold ${SEV_CHIP[sevOf(it.f.severity)]}`}>{SEV_LABEL[sevOf(it.f.severity)]}</span>
          <b className="min-w-0 break-words text-[14px] text-ink">{it.f.name}</b>
        </div>
        <div className="mono mt-1 break-all text-[12px] text-ink-faint">{it.f.url || it.f.host}</div>
        {it.f.impact && <p className="mt-2 break-words text-[13px] text-ink"><b>Impact. </b>{it.f.impact}</p>}
        {it.f.remediation && <p className="mt-1.5 break-words text-[13px] text-ink"><b>Remediation. </b>{it.f.remediation}</p>}
      </div>
    )
  }
}

export function ReportPreview({ tid, rev, canAudit, onRestored }: { tid: string; rev: number; canAudit: boolean; onRestored: () => void }) {
  const [c, setC] = useState<ContentView | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [tick, setTick] = useState(0)
  const [restoring, setRestoring] = useState(false)
  const versions = useRef<HTMLElement>(null)
  useEffect(() => {
    let live = true
    auditApi.content(tid).then((v) => { if (live) { setC(v); setErr(null) } }).catch((e) => { if (live && !c) setErr(e?.message || 'Could not load the preview.') })
    return () => { live = false }
  }, [tid, rev, tick])   // eslint-disable-line react-hooks/exhaustive-deps
  const restore = async (v: number) => {
    if (!c || restoring) return
    setRestoring(true)
    try {
      const r = await auditApi.restore(tid, v, c.version)
      toast(`Restored version ${v} as version ${r.version}`); onRestored()
      versions.current?.focus()   // the Restore button that was pressed goes away with the new version
    } catch { setTick((n) => n + 1) } finally { setRestoring(false) }
  }
  if (err) return <ErrorRetry message={err} onRetry={() => setTick((n) => n + 1)} />
  if (!c) return <div aria-busy="true" className="p-6 text-[13px] text-ink-faint">Loading the preview</div>
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-rule px-5 py-3 text-[12.5px] text-ink-muted">
        <span>Version {c.version} · {c.created_by} · {when(c.created_at)}</span>
        <details className="relative">
          <summary ref={versions} className="flex min-h-[44px] cursor-pointer items-center font-semibold text-accent-ink">Versions ({c.versions.length})</summary>
          <ul className="absolute right-0 z-10 mt-1 w-[min(92vw,360px)] space-y-1 rounded-input border border-rule bg-card p-2 shadow-lg">
            {c.versions.map((v) => (
              <li key={v.version} className="flex items-center gap-2 text-[12.5px] text-ink">
                <span className="min-w-0 flex-1 truncate" title={`v${v.version} · ${v.created_by} · ${v.note || 'edit'}`}>v{v.version} · {v.created_by} · {v.note || 'edit'}</span>
                {canAudit && v.version !== c.version && <Button size="sm" variant="outline" className="min-h-[44px] sm:min-h-0" disabled={restoring} onClick={() => restore(v.version)}>Restore</Button>}
              </li>
            ))}
          </ul>
        </details>
      </div>
      <div className="space-y-6 p-5">
        {c.preview.filter((s) => s.id !== 'cover').map((s) => (
          <section key={s.id}>
            <h3 className="mb-2.5 text-[15px] font-bold text-ink">{s.title}</h3>
            <div className="space-y-3">{groupItems(s.items as PreviewItem[]).map((it, i) => <Item key={i} it={it} />)}</div>
          </section>
        ))}
      </div>
    </div>
  )
}
