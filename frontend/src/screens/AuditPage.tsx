import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { ErrorRetry } from '@/components/ErrorRetry'
import { ShellActions, ShellTitle } from '@/components/ShellSlots'
import { AiChat } from '@/components/audit/AiChat'
import { FindingDrawer } from '@/components/audit/FindingDrawer'
import { ManualDrawer } from '@/components/audit/ManualDrawer'
import { PdfPanel } from '@/components/audit/PdfPanel'
import { ReportPreview } from '@/components/audit/ReportPreview'
import { Trail } from '@/components/audit/Trail'
import { TargetFindings } from '@/components/findings/TargetFindings'
import { Button } from '@/components/ui/button'
import { pdfBadge, auditApi, readOnlyReason, type AuditSummary } from '@/lib/audit'
import { SEVS, SEV_LABEL, patchRows, rowsKeyPrefix, type FindingRow } from '@/lib/findings'
import { bare } from '@/lib/format'
import { useReturnFocus } from '@/lib/returnFocus'
import { invalidate } from '@/lib/swr'
import { useApiData } from '@/lib/useApiData'

const card = 'overflow-hidden rounded-bento-lg border border-rule bg-card'
const cardOpen = 'rounded-bento-lg border border-rule bg-card'   // the Versions menu hangs out of its section: no clipping
const TONE = { low: 'bg-low-bg text-low-ink', med: 'bg-med-bg text-med-ink', info: 'bg-panel text-ink' }

export default function AuditRoute() {
  const { tid } = useParams()
  return tid ? <AuditPage key={tid} tid={tid} /> : null
}

function AuditPage({ tid }: { tid: string }) {
  const { data: sum, error, reload } = useApiData<AuditSummary>(() => auditApi.summary(tid), `prv:/api/tasks/${tid}/audit`)
  const [rev, setRev] = useState(0)           // bumped after any change: refetches the preview and the trail
  const [listRev, setListRev] = useState(0)   // bumped only when rows were added: remounts the findings list (page 1 again)
  const [sev, setSev] = useState<string>('')
  const [sel, setSel] = useState<FindingRow | null>(null)
  const [open, setOpen] = useState(false)
  const [adding, setAdding] = useState(false)
  const rowFocus = useReturnFocus()   // closing a drawer gives focus back to the row / button that opened it
  const addFocus = useReturnFocus()
  const refresh = () => { setRev((n) => n + 1); reload() }                        // report content, PDF or trail changed
  // A verdict or an edit changes one loaded row: patch it where it is, so the list keeps its place and its pages.
  const patched = (id: string, patch: Partial<FindingRow>) => {
    patchRows('prv', tid, id, patch)
    setSel((s) => (s && s.id === id ? { ...s, ...patch } : s))
  }
  const added = () => { invalidate(rowsKeyPrefix('prv', tid)); setListRev((n) => n + 1); refresh() }   // a new row: drop the cached pages

  if (!sum) return (
    <>
      <ShellTitle size="band" title="Audit report" />
      {error ? <ErrorRetry message={error} onRetry={reload} /> : <div className="p-10 text-ink-faint">Loading</div>}
    </>
  )
  const badge = pdfBadge(sum.pdf)
  const can = sum.can_audit

  return (
    <>
      <ShellTitle size="band" title="Audit report" kicker={`${sum.task.client} · ${bare(sum.task.target)}`} />
      <ShellActions>
        <Link to="/team" className="flex h-11 items-center rounded-pill bg-white/[.16] px-4 text-[13px] font-medium text-[#F2F5EF]">Board</Link>
        {can && <Button variant="glass" size="pill" onClick={() => { addFocus.remember(); setAdding(true) }}><Plus size={16} /> Add finding</Button>}
      </ShellActions>

      <div className="mt-3.5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-bento-lg bg-panel px-5 py-3.5 text-[13px] text-ink">
        <span><b>{sum.counts.tp}</b> confirmed</span>
        <span><b>{sum.counts.fp}</b> false positive</span>
        {sum.counts.manual > 0 && <span><b>{sum.counts.manual}</b> added by hand</span>}
        <span className="text-ink-muted">Report version {sum.content_version}</span>
        <span className={`rounded-pill px-3 py-1 text-[12px] font-semibold ${TONE[badge.tone]}`}>{badge.label}</span>
      </div>
      {!can && <p role="status" className="mt-3 rounded-input border border-rule bg-card px-4 py-3 text-[13px] text-ink">{readOnlyReason(sum)}</p>}

      <div className="mt-3.5 grid gap-3.5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <div className="space-y-3.5">
          <section className={card} aria-label="Findings">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-5 py-3">
              <h2 className="text-[15px] font-bold text-ink">Findings</h2>
              <select aria-label="Filter by severity" value={sev} onChange={(e) => setSev(e.target.value)} className="min-h-[44px] rounded-input border border-rule bg-panel px-3 text-[13px] capitalize text-ink">
                <option value="">All severities</option>
                {SEVS.map((s) => <option key={s} value={s}>{SEV_LABEL[s]}</option>)}
              </select>
            </div>
            <TargetFindings key={`${listRev}:${sev}`} plane="prv" taskId={tid} severity={sev || null} focusId={null} staff
              onOpen={(f) => { rowFocus.remember(); setSel(f); setOpen(true) }} onDismissFocus={() => {}} />
          </section>
          <section className={cardOpen} aria-label="Report preview">
            <h2 className="border-b border-rule px-5 py-3 text-[15px] font-bold text-ink">Report preview</h2>
            <ReportPreview tid={tid} rev={rev} canAudit={can} onRestored={refresh} />
          </section>
        </div>
        <aside className="space-y-3.5">
          <PdfPanel tid={tid} summary={sum} onChanged={refresh} />
          {sum.ai_chat && <AiChat tid={tid} summary={sum} onChanged={refresh} />}
          <Trail tid={tid} rev={rev} />
        </aside>
      </div>

      <FindingDrawer f={sel} open={open} onOpenChange={setOpen} tid={tid} canAudit={can} onCloseAutoFocus={rowFocus.onCloseAutoFocus} onPatched={patched} onChanged={refresh} />
      <ManualDrawer tid={tid} open={adding} onOpenChange={setAdding} onAdded={added} onCloseAutoFocus={addFocus.onCloseAutoFocus} />
    </>
  )
}
