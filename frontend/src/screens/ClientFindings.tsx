import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { Gauge } from '@/components/viz/Gauge'
import { SegBar } from '@/components/viz/SegBar'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { rise } from '@/lib/motion'

type F = {
  id: string; name: string; severity: string; asset: string; tool: string
  cve: string; verdict: 'tp' | 'fp'; status: string; evidence: string; remediation: string
}
const rank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
const sevLabel: Record<string, string> = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' }
const chip = 'rounded-md border border-rule bg-panel px-1.5 py-0.5 text-[11px] text-ink-muted'

export default function ClientFindings() {
  const [rows, setRows] = useState<F[] | null>(null)
  const [sel, setSel] = useState<F | null>(null)
  const [open, setOpen] = useState(false)
  useEffect(() => { api.get('/api/findings').then(setRows) }, [])

  const list = useMemo(
    () => (rows ?? []).filter((f) => f.verdict === 'tp').sort((a, b) => rank[a.severity] - rank[b.severity]),
    [rows],
  )
  const count = (s: string) => list.filter((f) => f.severity === s).length
  const fixed = list.filter((f) => f.status === 'fixed').length
  const openN = list.length - fixed
  const maxCount = Math.max(1, count('critical'), count('high'), count('medium'), count('low'))
  const resolvedPct = list.length ? Math.round((fixed / list.length) * 100) : 0

  useEffect(() => { if (rows) rise('.entry', 45) }, [rows])

  return (
    <ClientShell title="Findings" sub="Confirmed issues from your latest scan.">
      {!rows ? (
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
            <ul>
              {list.map((f, i) => {
                const resolved = f.status === 'fixed'
                return (
                  <li key={f.id} className="entry" style={{ opacity: 0 }}>
                    <button
                      onClick={() => { setSel(f); setOpen(true) }}
                      className="group flex w-full items-center gap-4 border-b border-rule px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-panel"
                    >
                      <span className="mono w-6 flex-none text-[12px] tabular-nums text-ink-faint">{String(i + 1).padStart(2, '0')}</span>
                      <span className="flex w-[74px] flex-none items-center gap-2">
                        <span className="h-2.5 w-2.5 flex-none rounded-full" style={{ background: `var(--color-${f.severity})`, opacity: resolved ? 0.4 : 1 }} />
                        <span className="text-[12px] text-ink-muted">{sevLabel[f.severity]}</span>
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className={`block truncate text-[15.5px] font-medium ${resolved ? 'text-ink-muted' : 'text-ink'}`}>{f.name}</span>
                        <span className="mono mt-0.5 block truncate text-[12px] text-ink-faint">{f.asset}</span>
                      </span>
                      <span className="hidden items-center gap-1.5 sm:flex">
                        <span className={chip} title={`Detected by ${f.tool}`}>{f.tool}</span>
                        <span className={chip} title="Weakness classification">{f.cve}</span>
                      </span>
                      {resolved
                        ? <span className="w-[76px] flex-none text-right text-[12px] font-medium text-low">Resolved</span>
                        : <span className="grid h-8 w-8 flex-none place-items-center rounded-full border border-rule text-ink-faint opacity-0 transition-all duration-200 group-hover:opacity-100 group-hover:text-ink sm:w-8"><ArrowUpRight size={15} /></span>}
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
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: `var(--color-${sel.severity})` }} />
                  <span className="text-[12px] text-ink-muted">{sevLabel[sel.severity]}</span>
                </div>
                <DrawerTitle className="mt-2 text-[23px] font-bold tracking-[-0.02em] text-ink">{sel.name}</DrawerTitle>
                <div className="mono mt-1.5 text-[13px] text-ink-muted">{sel.asset}</div>
                <div className="mt-2.5 flex gap-1.5">
                  <span className={chip}>{sel.tool}</span>
                  <span className={chip}>{sel.cve}</span>
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
                <p className="text-[15px] leading-relaxed text-ink">{sel.remediation}</p>
              </section>
            </div>
            <div className="sticky bottom-0 border-t border-rule bg-card p-6">
              <Button size="lg" className="w-full" disabled={sel.status === 'fixed'}>
                {sel.status === 'fixed' ? 'Resolved' : 'Mark as resolved'}
              </Button>
            </div>
          </DrawerContent>
        )}
      </Drawer>
    </ClientShell>
  )
}
