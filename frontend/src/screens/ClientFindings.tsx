import { useMemo, useState } from 'react'
import { ChevronDown, Filter } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientPage } from '@/components/ClientPage'
import { ErrorRetry } from '@/components/ErrorRetry'
import { Gauge } from '@/components/viz/Gauge'
import { SegBar } from '@/components/viz/SegBar'
import { TargetAccordion } from '@/components/findings/TargetAccordion'
import { TargetFindings } from '@/components/findings/TargetFindings'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { FEEDS } from '@/lib/feeds'
import { SEV_LABEL, patchRows, sevOf, sevVar, totalsOf, type FindingRow, type TargetRow } from '@/lib/findings'
import { bare } from '@/lib/format'
import { invalidate } from '@/lib/swr'
import { useApiData } from '@/lib/useApiData'
import { useFindingDetail } from '@/lib/useFindingDetail'
import { useFindingsUrl } from '@/lib/useFindingsUrl'

const chip = 'rounded-md border border-rule bg-panel px-1.5 py-0.5 text-[11px] text-ink-muted'

export default function ClientFindings() {
  const { data: targets, error, reload, fresh } = useApiData<TargetRow[]>(FEEDS.clientTargets.load, FEEDS.clientTargets.key)
  const url = useFindingsUrl()
  const [sel, setSel] = useState<FindingRow | null>(null)
  const [open, setOpen] = useState(false)
  const [site, setSite] = useState<string | null>(null)
  const { detail, failed } = useFindingDetail('pub', open && sel ? sel.id : null)

  // Portfolio-wide stats (severity bars, resolved gauge) stay unfiltered - the engagement filter only narrows
  // the accordion below, same as the team's severity filter narrows its list, not its totals.
  const sums = useMemo(() => totalsOf(targets ?? []), [targets])
  const sites = useMemo(() => [...new Set((targets ?? []).map((t) => bare(t.target)))].sort(), [targets])
  const shown = useMemo(() => (site ? (targets ?? []).filter((t) => bare(t.target) === site) : targets ?? []), [targets, site])
  const maxCount = Math.max(1, ...Object.values(sums.counts))
  const resolvedPct = sums.total ? Math.round((sums.fixed / sums.total) * 100) : 0
  // Only after a fresh answer: a stale cache must not claim a brand-new target does not exist.
  const lost = !!url.target && !!targets && fresh && !targets.some((t) => t.task_id === url.target)

  const openRow = (f: FindingRow) => { setSel(f); setOpen(true); url.set({ finding: f.id }) }

  const markResolved = (f: FindingRow) => {
    patchRows('pub', f.task_id, f.id, { status: 'fixed' })
    setSel({ ...f, status: 'fixed' })
    api.post(`/api/findings/${f.id}/status`, { status: 'fixed' })
      .then(() => { reload(); invalidate(FEEDS.cockpit.key) })
      .catch(() => {
        // Revert the optimistic flip - api.ts already toasted why it failed.
        patchRows('pub', f.task_id, f.id, { status: 'open' })
        setSel((s) => (s && s.id === f.id ? { ...s, status: 'open' } : s))
      })
  }

  return (
    <ClientPage
      title="Findings"
      sub="Confirmed issues across your scans, grouped by target."
      action={
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="glass" size="pill"><Filter size={15} /> {site ?? 'All engagements'} <ChevronDown size={14} /></Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setSite(null)}>All engagements</DropdownMenuItem>
            <DropdownMenuSeparator />
            {sites.map((s) => <DropdownMenuItem key={s} onClick={() => setSite(s)}>{s}</DropdownMenuItem>)}
          </DropdownMenuContent>
        </DropdownMenu>
      }
    >
      {error ? (
        <ErrorRetry message={error} onRetry={reload} />
      ) : !targets ? (
        <div className="p-10 text-ink-faint">Loading</div>
      ) : (
        <div className="flex flex-col gap-3">
          {/* Summary: severity distribution + resolution gauge */}
          <section className="grid grid-cols-1 gap-6 rounded-bento border border-rule bg-card p-6 lg:grid-cols-[1fr_auto] lg:gap-10">
            <div className="min-w-0">
              <div className="flex items-baseline gap-2.5">
                <span className="font-display text-[46px] font-bold leading-none tracking-[-0.03em] text-ink">{sums.open}</span>
                <span className="text-[14px] text-ink-muted">open of {sums.total}</span>
              </div>
              <div className="mt-6 flex flex-col gap-3">
                <SegBar label="Critical" count={sums.counts.critical} max={maxCount} tone="crit" />
                <SegBar label="High" count={sums.counts.high} max={maxCount} tone="high" />
                <SegBar label="Medium" count={sums.counts.medium} max={maxCount} tone="med" />
                <SegBar label="Low" count={sums.counts.low} max={maxCount} tone="low" />
                <SegBar label="Info" count={sums.counts.info} max={maxCount} tone="info" />
              </div>
            </div>
            <div className="flex items-center justify-center border-t border-rule pt-4 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
              <Gauge value={resolvedPct} label="Resolved" tone="low" />
            </div>
          </section>

          {lost && (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-bento border border-rule bg-card px-5 py-4 text-[13.5px] text-ink">
              <span>That target was not found. It may have been removed, or it is not part of your account.</span>
              <Button variant="outline" size="sm" className="min-h-[44px]" onClick={() => url.set({ target: null, finding: null })}>Show all targets</Button>
            </div>
          )}

          {/* One row per target; the open one shows its findings, 100 at a time. */}
          <section className="rounded-bento border border-rule bg-card">
            {shown.length === 0 && <div className="px-5 py-10 text-center text-[13px] text-ink-faint">{site ? `No findings for ${site}.` : 'No confirmed findings yet.'}</div>}
            <TargetAccordion
              targets={shown}
              openId={url.target}
              staff={false}
              onToggle={(id) => url.set({ target: id, finding: null })}
              renderPanel={(t) => (
                <TargetFindings
                  plane="pub"
                  taskId={t.task_id}
                  severity={null}
                  focusId={url.finding}
                  staff={false}
                  onOpen={openRow}
                  onDismissFocus={() => url.set({ finding: null })}
                />
              )}
            />
          </section>
        </div>
      )}

      <Drawer open={open} onOpenChange={setOpen}>
        {sel && (
          <DrawerContent>
            <div className="flex items-start justify-between gap-4 border-b border-rule p-6">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: `var(--color-${sevVar(sel.severity)})` }} />
                  <span className="text-[12px] text-ink-muted">{SEV_LABEL[sevOf(sel.severity)]}</span>
                </div>
                <DrawerTitle className="mt-2 text-[23px] font-bold tracking-[-0.02em] text-ink">{sel.name}</DrawerTitle>
                <div className="mono mt-1.5 text-[13px] text-ink-muted">{sel.url || sel.host}</div>
                <div className="mt-2.5 flex gap-1.5">
                  <span className={chip}>{sel.tool || '-'}</span>
                  <span className={chip}>{sel.cve ?? sel.cwe ?? '-'}</span>
                </div>
              </div>
            </div>
            <div className="flex-1 space-y-6 p-6">
              <section>
                <h4 className="mb-2 text-[12px] font-medium uppercase tracking-wide text-ink-faint">Evidence</h4>
                <pre className="overflow-x-auto rounded-input border border-rule bg-panel p-3.5 font-mono text-[12px] leading-relaxed text-ink">{detail ? detail.evidence : failed ? 'Could not load the details.' : 'Loading'}</pre>
              </section>
              <section>
                <h4 className="mb-2 text-[12px] font-medium uppercase tracking-wide text-ink-faint">Remediation</h4>
                <p className="text-[15px] leading-relaxed text-ink">{detail ? detail.remediation ?? 'Not yet enriched.' : failed ? 'Could not load the details.' : 'Loading'}</p>
              </section>
            </div>
            <div className="sticky bottom-0 border-t border-rule bg-card p-6">
              <Button size="lg" className="w-full" disabled={sel.status === 'fixed'} onClick={() => markResolved(sel)}>
                {sel.status === 'fixed' ? 'Resolved' : 'Mark as resolved'}
              </Button>
            </div>
          </DrawerContent>
        )}
      </Drawer>
    </ClientPage>
  )
}
