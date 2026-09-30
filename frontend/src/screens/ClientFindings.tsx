import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, ChevronDown, Filter } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { ErrorRetry } from '@/components/ErrorRetry'
import { Gauge } from '@/components/viz/Gauge'
import { SegBar } from '@/components/viz/SegBar'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { useApiData } from '@/lib/useApiData'
import { rise } from '@/lib/motion'

type F = {
  id: string; name: string; severity: string; host: string; url: string; tool: string
  cve?: string | null; verdict: 'tp' | 'fp'; status: string; evidence: string; remediation?: string | null
}
const rank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
const sevLabel: Record<string, string> = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' }
// The colour tokens are --color-crit / --color-med; asking for --color-critical drew no dot at all.
const sevVar = (s: string) => ({ critical: 'crit', medium: 'med' } as Record<string, string>)[s] ?? s
const chip = 'rounded-md border border-rule bg-panel px-1.5 py-0.5 text-[11px] text-ink-muted'
const assetOf = (f: F) => f.url || f.host

// Findings carry a host (and optionally a more specific url), not a separate engagement tag -
// this derives which site a finding belongs to from that field directly, so the filter reflects
// real data instead of a hand-maintained mapping that could drift from it.
const siteOf = (f: F) => f.host

export default function ClientFindings() {
  const { data: rows, error, reload, setData: setRows } = useApiData<F[]>(() => api.get('/api/findings'))
  const [sel, setSel] = useState<F | null>(null)
  const [open, setOpen] = useState(false)
  const [site, setSite] = useState<string | null>(null)

  const list = useMemo(
    () => (rows ?? []).filter((f) => f.verdict === 'tp').sort((a, b) => rank[a.severity] - rank[b.severity]),
    [rows],
  )
  // Portfolio-wide stats (severity bars, resolved gauge) stay unfiltered - the site filter only
  // narrows the register below, same as team's severity filter narrows its list, not its totals.
  const sites = useMemo(() => [...new Set(list.map(siteOf))].sort(), [list])
  const filteredList = useMemo(() => (site ? list.filter((f) => siteOf(f) === site) : list), [list, site])
  const count = (s: string) => list.filter((f) => f.severity === s).length
  const fixed = list.filter((f) => f.status === 'fixed').length
  const openN = list.length - fixed
  const maxCount = Math.max(1, count('critical'), count('high'), count('medium'), count('low'))
  const resolvedPct = list.length ? Math.round((fixed / list.length) * 100) : 0

  useEffect(() => { if (rows) rise('.entry', 45) }, [rows])

  return (
    <ClientShell
      title="Findings"
      sub="Confirmed issues from your latest scan."
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
      ) : !rows ? (
        <div className="p-10 text-ink-faint">Loading</div>
      ) : (
        <div className="flex flex-col gap-3">
          {/* Summary: severity distribution + resolution gauge */}
          <section className="grid grid-cols-1 gap-6 rounded-bento border border-rule bg-card p-6 lg:grid-cols-[1fr_auto] lg:gap-10">
            <div className="min-w-0">
              <div className="flex items-baseline gap-2.5">
                <span className="font-display text-[46px] font-bold leading-none tracking-[-0.03em] text-ink">{openN}</span>
                <span className="text-[14px] text-ink-muted">open of {list.length}</span>
              </div>
              <div className="mt-6 flex flex-col gap-3">
                <SegBar label="Critical" count={count('critical')} max={maxCount} tone="crit" />
                <SegBar label="High" count={count('high')} max={maxCount} tone="high" />
                <SegBar label="Medium" count={count('medium')} max={maxCount} tone="med" />
                <SegBar label="Low" count={count('low')} max={maxCount} tone="low" />
              </div>
            </div>
            <div className="flex items-center justify-center border-t border-rule pt-4 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
              <Gauge value={resolvedPct} label="Resolved" tone="low" />
            </div>
          </section>

          {/* Register */}
          <section className="rounded-bento border border-rule bg-card">
            {filteredList.length === 0 && <div className="px-5 py-10 text-center text-[13px] text-ink-faint">No findings for {site}.</div>}
            <ul>
              {filteredList.map((f) => {
                const resolved = f.status === 'fixed'
                return (
                  <li key={f.id} className="entry" style={{ opacity: 0 }}>
                    <button
                      onClick={() => { setSel(f); setOpen(true) }}
                      className="group grid min-h-[68px] w-full grid-cols-[1fr_auto] items-start gap-x-3 gap-y-1.5 border-b border-rule px-4 py-4 text-left transition-colors last:border-b-0 hover:bg-panel focus-visible:bg-panel focus-visible:outline-none sm:flex sm:items-center sm:gap-4 sm:px-5"
                    >
                      {/* Phone: severity + state on the first line, the full title (wrapping) below.
                          The old row squeezed the title to "SQL I…" between fixed columns. The
                          position number is gone: it renumbered with every filter, so it meant nothing. */}
                      <span className="col-start-1 row-start-1 flex items-center gap-2 sm:w-[74px] sm:flex-none">
                        <span className="h-2.5 w-2.5 flex-none rounded-full" style={{ background: `var(--color-${sevVar(f.severity)})`, opacity: resolved ? 0.4 : 1 }} />
                        <span className="text-[12px] text-ink-muted">{sevLabel[f.severity]}</span>
                      </span>
                      <span className="col-span-2 row-start-2 min-w-0 sm:col-auto sm:row-auto sm:flex-1">
                        <span className={`line-clamp-2 block text-[15.5px] font-medium leading-snug sm:line-clamp-none sm:truncate ${resolved ? 'text-ink-muted' : 'text-ink'}`}>{f.name}</span>
                        <span className="mono mt-0.5 block truncate text-[12px] text-ink-faint">{assetOf(f)}</span>
                      </span>
                      <span className="hidden items-center gap-1.5 sm:flex">
                        <span className={chip} title={`Detected by ${f.tool}`}>{f.tool}</span>
                        <span className={chip} title="Weakness classification">{f.cve ?? '—'}</span>
                      </span>
                      {resolved
                        ? <span className="col-start-2 row-start-1 flex-none text-right text-[12px] font-medium text-low sm:w-[76px]">Resolved</span>
                        : <span className="col-start-2 row-start-1 grid h-8 w-8 flex-none place-items-center rounded-full border border-rule text-ink-faint transition-opacity duration-200 group-hover:text-ink sm:opacity-0 sm:group-hover:opacity-100"><ArrowUpRight size={15} /></span>}
                    </button>
                  </li>
                )
              })}
            </ul>
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
                  <span className="text-[12px] text-ink-muted">{sevLabel[sel.severity]}</span>
                </div>
                <DrawerTitle className="mt-2 text-[23px] font-bold tracking-[-0.02em] text-ink">{sel.name}</DrawerTitle>
                <div className="mono mt-1.5 text-[13px] text-ink-muted">{assetOf(sel)}</div>
                <div className="mt-2.5 flex gap-1.5">
                  <span className={chip}>{sel.tool}</span>
                  <span className={chip}>{sel.cve ?? '—'}</span>
                </div>
              </div>
            </div>
            <div className="flex-1 space-y-6 p-6">
              <section>
                <h4 className="mb-2 text-[12px] font-medium uppercase tracking-wide text-ink-faint">Evidence</h4>
                <pre className="overflow-x-auto rounded-input border border-rule bg-panel p-3.5 font-mono text-[12px] leading-relaxed text-ink">{sel.evidence}</pre>
              </section>
              <section>
                <h4 className="mb-2 text-[12px] font-medium uppercase tracking-wide text-ink-faint">Remediation</h4>
                <p className="text-[15px] leading-relaxed text-ink">{sel.remediation ?? 'Not yet enriched.'}</p>
              </section>
            </div>
            <div className="sticky bottom-0 border-t border-rule bg-card p-6">
              <Button
                size="lg"
                className="w-full"
                disabled={sel.status === 'fixed'}
                onClick={() => {
                  setRows((rs) => rs?.map((f) => (f.id === sel.id ? { ...f, status: 'fixed' } : f)) ?? rs)
                  setSel({ ...sel, status: 'fixed' })
                  api.post(`/api/findings/${sel.id}/status`, { status: 'fixed' }).catch(() => {
                    // Revert the optimistic flip - api.ts already toasted why it failed.
                    setRows((rs) => rs?.map((f) => (f.id === sel.id ? { ...f, status: 'open' } : f)) ?? rs)
                    setSel((s) => (s && s.id === sel.id ? { ...s, status: 'open' } : s))
                  })
                }}
              >
                {sel.status === 'fixed' ? 'Resolved' : 'Mark as resolved'}
              </Button>
            </div>
          </DrawerContent>
        )}
      </Drawer>
    </ClientShell>
  )
}
