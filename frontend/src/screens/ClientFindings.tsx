import { useEffect, useMemo, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'

type F = {
  id: string; name: string; severity: string; asset: string; tool: string
  cve: string; verdict: 'tp' | 'fp'; status: string; evidence: string; remediation: string
}
const sevPill: Record<string, string> = {
  critical: 'bg-crit-bg text-crit', high: 'bg-high-bg text-high', medium: 'bg-med-bg text-med', low: 'bg-low-bg text-low',
}
const sevDot: Record<string, string> = { critical: 'bg-crit', high: 'bg-high', medium: 'bg-med', low: 'bg-low' }
const statusPill: Record<string, string> = { open: 'bg-accent-soft text-accent-ink', fixed: 'bg-low-bg text-low' }
const rank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }

// Client-facing remediation list: your own confirmed findings (FPs already filtered by the team),
// sorted by severity, with evidence + fix guidance. Read-only — you can only track your own fixes.
export default function ClientFindings() {
  const [rows, setRows] = useState<F[] | null>(null)
  const [sel, setSel] = useState<F | null>(null)
  const [open, setOpen] = useState(false)
  useEffect(() => { api.get('/api/findings').then(setRows) }, [])

  const list = useMemo(
    () => (rows ?? []).filter((f) => f.verdict === 'tp').sort((a, b) => rank[a.severity] - rank[b.severity]),
    [rows],
  )

  return (
    <ClientShell title="Findings" sub="Confirmed issues from your latest assessment, prioritized by severity.">
      {!rows ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="overflow-hidden rounded-bento border border-rule bg-card">
          <div className="grid grid-cols-[90px_1fr_90px] gap-4 border-b border-rule px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint sm:grid-cols-[100px_1fr_1fr_90px]">
            <span>Severity</span><span>Finding</span><span className="hidden sm:block">Asset</span><span className="text-right sm:text-left">Status</span>
          </div>
          {list.map((f) => (
            <button
              key={f.id}
              onClick={() => { setSel(f); setOpen(true) }}
              className="grid w-full grid-cols-[90px_1fr_90px] items-center gap-4 border-b border-rule px-5 py-3.5 text-left transition-colors last:border-0 hover:bg-panel sm:grid-cols-[100px_1fr_1fr_90px]"
            >
              <span className={`inline-flex items-center gap-1.5 justify-self-start rounded-md px-2 py-1 text-[11px] font-bold capitalize ${sevPill[f.severity]}`}><span className={`h-1.5 w-1.5 rounded-full ${sevDot[f.severity]}`} />{f.severity}</span>
              <span className="min-w-0"><span className="block truncate text-[14px] font-semibold text-ink">{f.name}</span><span className="text-[11.5px] text-ink-faint">{f.tool} · {f.cve}</span></span>
              <span className="hidden truncate font-mono text-[12px] text-ink-muted sm:block">{f.asset}</span>
              <span className={`justify-self-end rounded-pill px-2.5 py-1 text-[11px] font-semibold capitalize sm:justify-self-start ${statusPill[f.status]}`}>{f.status}</span>
            </button>
          ))}
        </div>
      )}

      <Drawer open={open} onOpenChange={setOpen}>
        {sel && (
          <DrawerContent>
            <div className="border-b border-rule p-6">
              <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-bold capitalize ${sevPill[sel.severity]}`}><span className={`h-1.5 w-1.5 rounded-full ${sevDot[sel.severity]}`} />{sel.severity}</span>
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
