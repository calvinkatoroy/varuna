import { useEffect, useMemo, useState } from 'react'
import { Check, ChevronsUp, ChevronRight, CircleAlert, Clock, ShieldCheck, TriangleAlert } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { StatRing } from '@/components/StatRing'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { revealTiles } from '@/lib/motion'

type F = {
  id: string; name: string; severity: string; asset: string; tool: string
  cve: string; verdict: 'tp' | 'fp'; status: string; evidence: string; remediation: string
}
const sevPill: Record<string, string> = {
  critical: 'bg-crit-bg text-crit', high: 'bg-high-bg text-high', medium: 'bg-med-bg text-med', low: 'bg-low-bg text-low',
}
const sevBar: Record<string, string> = { critical: 'bg-crit', high: 'bg-high', medium: 'bg-med', low: 'bg-low' }
const rank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }

// Client-facing remediation view: your confirmed findings (FPs already filtered by the team),
// led by a severity ledger and stacked as severity-spined cards — same language as the cockpit.
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

  useEffect(() => { if (rows) revealTiles('.tile') }, [rows])

  return (
    <ClientShell title="Findings" sub="Confirmed issues from your latest assessment, prioritized by severity.">
      {!rows ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,340px)_minmax(0,1fr)]">
          {/* Severity ledger */}
          <section className="tile flex flex-col rounded-bento border border-rule bg-card-2 p-5 lg:sticky lg:top-4 lg:self-start" style={{ opacity: 0 }}>
            <h3 className="text-[16px] font-bold tracking-[-0.02em] text-ink">Severity ledger</h3>
            <p className="mt-1 text-[12.5px] text-ink-muted">{list.length} confirmed · {fixed} fixed</p>
            <div className="mt-5 grid grid-cols-2 gap-x-5 gap-y-5">
              <StatRing tone="c" n={count('critical')} label="Critical" icon={<TriangleAlert size={20} />} />
              <StatRing tone="h" n={count('high')} label="High" icon={<ChevronsUp size={20} />} />
              <StatRing tone="m" n={count('medium')} label="Medium" icon={<CircleAlert size={20} />} />
              <StatRing tone="l" n={count('low')} label="Low" icon={<Check size={20} />} />
              <StatRing tone="o" n={list.length - fixed} unit={`/ ${list.length}`} label="Still open" icon={<Clock size={20} />} />
              <StatRing tone="s" n={fixed} label="Resolved" icon={<ShieldCheck size={20} />} />
            </div>
          </section>

          {/* Finding cards, severity-spined */}
          <div className="flex flex-col gap-2.5">
            {list.map((f) => (
              <button
                key={f.id}
                onClick={() => { setSel(f); setOpen(true) }}
                className="tile group flex items-stretch overflow-hidden rounded-bento border border-rule bg-card text-left transition-colors hover:border-ink/25"
                style={{ opacity: 0 }}
              >
                <span className={`w-1.5 flex-none ${sevBar[f.severity]}`} />
                <div className="flex min-w-0 flex-1 items-center gap-4 py-4 pl-4 pr-3.5">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2.5">
                      <span className={`rounded-md px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide ${sevPill[f.severity]}`}>{f.severity}</span>
                      <span className="truncate text-[15px] font-semibold text-ink">{f.name}</span>
                      {f.status === 'fixed' && <span className="rounded-pill bg-low-bg px-2 py-0.5 text-[10.5px] font-semibold text-low">Fixed</span>}
                    </div>
                    <div className="mt-1.5 text-[12px] text-ink-muted"><span className="font-mono text-ink-faint">{f.asset}</span> · {f.tool} · {f.cve}</div>
                  </div>
                  <ChevronRight size={18} className="flex-none text-ink-faint transition-colors group-hover:text-ink" />
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      <Drawer open={open} onOpenChange={setOpen}>
        {sel && (
          <DrawerContent>
            <div className="border-b border-rule p-6">
              <span className={`inline-block rounded-md px-2 py-0.5 text-[10.5px] font-bold uppercase tracking-wide ${sevPill[sel.severity]}`}>{sel.severity}</span>
              <DrawerTitle className="mt-2.5 text-[21px] font-bold tracking-[-0.02em] text-ink">{sel.name}</DrawerTitle>
              <div className="mt-1 font-mono text-[13px] text-ink-muted">{sel.asset}</div>
              <div className="mt-1 text-[12.5px] text-ink-faint">{sel.tool} · {sel.cve}</div>
            </div>
            <div className="flex-1 space-y-6 p-6">
              <section>
                <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Evidence</h4>
                <pre className="overflow-x-auto rounded-input border border-rule bg-panel p-3 font-mono text-[12px] leading-relaxed text-ink">{sel.evidence}</pre>
              </section>
              <section>
                <h4 className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint"><ShieldCheck size={13} className="text-accent" /> How to fix</h4>
                <p className="text-[13.5px] leading-relaxed text-ink">{sel.remediation}</p>
              </section>
            </div>
            <div className="sticky bottom-0 border-t border-rule bg-card p-6">
              <Button size="lg" className="w-full" disabled={sel.status === 'fixed'}>
                {sel.status === 'fixed' ? 'Marked as fixed' : 'Mark as fixed'}
              </Button>
            </div>
          </DrawerContent>
        )}
      </Drawer>
    </ClientShell>
  )
}
