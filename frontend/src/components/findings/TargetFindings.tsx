import { useEffect, useRef } from 'react'
import { ArrowUpRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ErrorRetry } from '@/components/ErrorRetry'
import { restoring } from '@/lib/scroll'
import { useTargetFindings } from '@/lib/useTargetFindings'
import { SEV_LABEL, sevOf, sevVar, type FindingRow, type Plane } from '@/lib/findings'

const chip = 'rounded-md border border-rule bg-panel px-1.5 py-0.5 text-[12px] text-ink-muted'
const statusPill: Record<string, string> = {
  open: 'bg-accent-soft text-accent-ink', fixed: 'bg-low-bg text-low-ink', accepted: 'bg-panel text-ink-muted',
}

function FindingRowView({ f, staff, highlight, onOpen }: { f: FindingRow; staff: boolean; highlight: boolean; onOpen: (f: FindingRow) => void }) {
  const resolved = f.status === 'fixed'
  return (
    <button
      id={`f-${f.id}`}
      type="button"
      onClick={() => onOpen(f)}
      aria-current={highlight ? 'true' : undefined}
      className={`group scroll-mt-24 grid min-h-[68px] w-full grid-cols-[1fr_auto] items-start gap-x-3 gap-y-1.5 border-b border-rule px-4 py-3.5 text-left transition-colors hover:bg-panel focus-visible:bg-panel focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus sm:flex sm:items-center sm:gap-4 sm:px-5 ${highlight ? 'bg-accent-soft' : ''}`}
    >
      {/* Phone: severity (dot + word) and state on the first line, the full wrapping title below. */}
      <span className="col-start-1 row-start-1 flex items-center gap-2 sm:w-[84px] sm:flex-none">
        <span aria-hidden className="h-2.5 w-2.5 flex-none rounded-full" style={{ background: `var(--color-${sevVar(f.severity)})`, opacity: resolved ? 0.4 : 1 }} />
        <span className="text-[12px] text-ink-muted" title={sevOf(f.severity) === f.severity ? undefined : f.severity}>{SEV_LABEL[sevOf(f.severity)]}</span>
      </span>
      <span className="col-span-2 row-start-2 min-w-0 sm:col-auto sm:row-auto sm:flex-1">
        <span className={`line-clamp-2 block text-[15.5px] font-medium leading-snug sm:line-clamp-none sm:truncate ${resolved ? 'text-ink-muted' : 'text-ink'}`}>{f.name}</span>
        <span className="mono mt-0.5 block truncate text-[12px] text-ink-faint">{f.url || f.host}</span>
      </span>
      <span className="hidden items-center gap-1.5 sm:flex">
        <span className={chip} title={`Detected by ${f.tool}`}>{f.tool || '-'}</span>
        <span className={chip} title="Weakness classification">{f.cve ?? f.cwe ?? '-'}</span>
      </span>
      {staff ? (
        <span className="col-start-2 row-start-1 flex flex-none items-center justify-end gap-2 sm:w-[170px]">
          <span className={`text-[12px] font-bold uppercase ${f.verdict === 'tp' ? 'text-low-ink' : 'text-ink-muted'}`}>{f.verdict === 'tp' ? 'TP' : 'FP'}</span>
          <span className={`rounded-pill px-2.5 py-1 text-[12px] font-semibold capitalize ${statusPill[f.status] ?? 'bg-panel text-ink-muted'}`}>{f.status}</span>
        </span>
      ) : resolved ? (
        <span className="col-start-2 row-start-1 flex-none text-right text-[12px] font-medium text-low-ink sm:w-[76px]">Resolved</span>
      ) : (
        <span aria-hidden className="col-start-2 row-start-1 grid h-8 w-8 flex-none place-items-center rounded-full border border-rule text-ink-faint transition-opacity duration-200 group-hover:text-ink sm:opacity-0 sm:group-hover:opacity-100"><ArrowUpRight size={15} /></span>
      )}
    </button>
  )
}

export function TargetFindings({ plane, taskId, severity, focusId, staff, onOpen, onDismissFocus }: {
  plane: Plane; taskId: string; severity: string | null; focusId: string | null; staff: boolean
  onOpen: (f: FindingRow) => void; onDismissFocus: () => void
}) {
  const { state, error, gone, focusLost, busy, loadMore, retry } = useTargetFindings(plane, taskId, severity, focusId)

  // Deep link: once the rows are there, bring the linked row to the middle of the screen (instant, no animation).
  const deepLink = useRef(focusId)
  const scrolled = useRef(false)
  // Back/Forward onto a link that names a finding: the saved scroll position wins over re-centring the row.
  useEffect(() => { if (restoring.on) scrolled.current = true }, [])
  useEffect(() => {
    if (!deepLink.current || scrolled.current || !state) return
    const el = document.getElementById(`f-${deepLink.current}`)
    if (!el) return
    scrolled.current = true
    el.scrollIntoView({ block: 'center' })
  }, [state])

  if (gone) return <div role="status" className="px-5 py-8 text-center text-[13px] text-ink-muted">This target is no longer available.</div>
  if (error && !state) return <ErrorRetry message={error} onRetry={retry} />
  if (!state) return <div aria-busy="true" className="px-5 py-8 text-[13px] text-ink-faint">Loading findings</div>

  const left = state.total - state.items.length
  const more = async () => {
    const first = await loadMore()
    if (first) requestAnimationFrame(() => document.getElementById(`f-${first}`)?.focus())
  }

  return (
    <div>
      {focusLost && focusId && (
        <div role="status" className="flex flex-wrap items-center justify-between gap-3 border-b border-rule bg-panel px-4 py-3 text-[13px] text-ink sm:px-5">
          <span>The finding in this link is not in this view. It may have been removed, belong to another account{severity ? ', or be hidden by the severity filter' : ''}.</span>
          <Button variant="outline" size="sm" className="min-h-[44px]" onClick={onDismissFocus}>Dismiss</Button>
        </div>
      )}
      {state.items.length === 0 && <div className="px-5 py-8 text-center text-[13px] text-ink-faint">{severity ? `No ${severity} findings in this target.` : 'No findings in this target.'}</div>}
      <ul>
        {state.items.map((f) => (
          <li key={f.id} className="row-defer">
            <FindingRowView f={f} staff={staff} highlight={f.id === focusId} onOpen={onOpen} />
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-5">
        <p role="status" className="text-[12px] text-ink-muted">Showing {state.items.length} of {state.total}</p>
        {left > 0 && <Button variant="outline" size="lg" className="min-h-[44px]" disabled={busy} onClick={more}>{busy ? 'Loading' : `Load more (${left} left)`}</Button>}
      </div>
      {error && <p role="alert" className="px-5 pb-3 text-[12px] text-crit">{error}</p>}
    </div>
  )
}
