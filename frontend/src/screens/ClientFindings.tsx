import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { DossierDefs, SeverityTally, VerdictStamp } from '@/components/marks/dossier'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { inkSettle } from '@/lib/motion'

type F = {
  id: string; name: string; severity: string; asset: string; tool: string
  cve: string; verdict: 'tp' | 'fp'; status: string; evidence: string; remediation: string
}
const rank: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
const sevLabel: Record<string, string> = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' }

// The client Findings page as a case-file dossier: an editorial masthead, a typographic
// assessment summary, and findings kept as ruled register entries with inked verdict stamps.
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
  const assets = new Set(list.map((f) => f.asset)).size

  useEffect(() => { if (rows) inkSettle('.entry') }, [rows])

  const ledger = [
    { n: count('critical'), label: 'Critical', tone: 'crit' },
    { n: count('high'), label: 'High', tone: 'high' },
    { n: count('medium'), label: 'Medium', tone: 'med' },
    { n: count('low'), label: 'Low', tone: 'low' },
    { n: list.length - fixed, label: 'Open', tone: 'ink' },
    { n: fixed, label: 'Resolved', tone: 'low' },
  ]

  return (
    <ClientShell title="Findings" sub="Confirmed issues from your latest assessment, kept as a case file.">
      {!rows ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="paper-grain relative overflow-hidden rounded-bento border border-rule bg-card">
          <DossierDefs />

          {/* Masthead */}
          <header className="flex flex-wrap items-start justify-between gap-6 px-[clamp(20px,3vw,40px)] pb-6 pt-[clamp(22px,3vw,36px)]">
            <div>
              <div className="mono text-[11px] uppercase tracking-[0.28em] text-ink-faint">Case file</div>
              <h1 className="mt-2 max-w-[18ch] font-serif text-[clamp(26px,3.4vw,40px)] font-semibold leading-[1.05] tracking-[-0.01em] text-ink">
                Acme Web App — Security Assessment
              </h1>
              <div className="mono mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-ink-muted">
                <span>No. AC-WEB-0712</span>
                <span>Opened Jun 20, 2026</span>
                <span>Examiner · Aisah R.</span>
              </div>
            </div>
            <VerdictStamp label="Confidential" tone="crit" tilt={5} delay={200} />
          </header>

          <div className="mx-[clamp(20px,3vw,40px)] border-t-2 border-ink/15" />

          {/* Assessment summary */}
          <section className="px-[clamp(20px,3vw,40px)] py-7">
            <h2 className="mono text-[11px] uppercase tracking-[0.28em] text-ink-faint">Assessment summary</h2>
            <p className="mt-3 max-w-[52ch] font-serif text-[clamp(15px,1.4vw,17px)] italic leading-relaxed text-ink-muted">
              {list.length} issues confirmed across {assets} assets.{' '}
              {count('critical') > 0 && <span className="not-italic font-medium text-ink">{count('critical')} critical require immediate remediation.</span>}
            </p>
            <div className="mt-6 flex flex-wrap gap-x-11 gap-y-5">
              {ledger.map((it) => (
                <div key={it.label}>
                  <div className="font-serif text-[38px] leading-none tracking-[-0.01em]" style={{ color: `var(--color-${it.tone})` }}>
                    {String(it.n).padStart(2, '0')}
                  </div>
                  <div className="mono mt-2 text-[10.5px] uppercase tracking-[0.16em] text-ink-faint">{it.label}</div>
                </div>
              ))}
            </div>
          </section>

          <div className="mx-[clamp(20px,3vw,40px)] border-t border-rule" />

          {/* Findings register */}
          <section className="px-[clamp(20px,3vw,40px)] pb-8 pt-7">
            <h2 className="mono mb-1 text-[11px] uppercase tracking-[0.28em] text-ink-faint">Findings register</h2>
            <ul>
              {list.map((f, i) => (
                <li key={f.id}>
                  <button
                    onClick={() => { setSel(f); setOpen(true) }}
                    className="entry group flex w-full items-center gap-5 border-b border-rule py-5 text-left"
                    style={{ opacity: 0 }}
                  >
                    <span className="mono w-9 flex-none text-[13px] tabular-nums text-ink-faint">{String(i + 1).padStart(2, '0')}</span>
                    <span className="flex w-12 flex-none items-center justify-center"><SeverityTally severity={f.severity} /></span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-serif text-[19px] font-medium leading-tight text-ink">{f.name}</span>
                      <span className="mono mt-1 block text-[12px] text-ink-muted"><span className="text-ink-faint">{f.asset}</span> · {f.tool} · {f.cve}</span>
                    </span>
                    <span className="hidden flex-none sm:block">
                      {f.status === 'fixed'
                        ? <VerdictStamp label="Resolved" tone="low" tilt={-6} size="sm" delay={280 + i * 90} />
                        : <VerdictStamp label={sevLabel[f.severity]} tone={f.severity} tilt={-8} size="sm" delay={280 + i * 90} />}
                    </span>
                    <span className="mono flex-none text-[12px] font-medium text-ink-faint transition-colors group-hover:text-accent">Open →</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}

      <Drawer open={open} onOpenChange={setOpen}>
        {sel && (
          <DrawerContent className="paper-grain">
            <DossierDefs />
            <div className="flex items-start justify-between gap-4 border-b border-rule p-6">
              <div>
                <div className="mono text-[10.5px] uppercase tracking-[0.24em] text-ink-faint">{sevLabel[sel.severity]} · {sel.cve}</div>
                <DrawerTitle className="mt-2 font-serif text-[24px] font-semibold leading-tight text-ink">{sel.name}</DrawerTitle>
                <div className="mono mt-1.5 text-[13px] text-ink-muted">{sel.asset} · {sel.tool}</div>
              </div>
              {sel.status === 'fixed'
                ? <VerdictStamp label="Resolved" tone="low" tilt={6} delay={220} />
                : <VerdictStamp label="Confirmed" tone={sel.severity} tilt={6} delay={220} />}
            </div>
            <div className="flex-1 space-y-7 p-6">
              <section>
                <h4 className="mono mb-2.5 text-[10.5px] uppercase tracking-[0.24em] text-ink-faint">Evidence</h4>
                <pre className="overflow-x-auto rounded-input border border-rule bg-panel p-3.5 font-mono text-[12px] leading-relaxed text-ink">{sel.evidence}</pre>
              </section>
              <section>
                <h4 className="mono mb-2.5 text-[10.5px] uppercase tracking-[0.24em] text-ink-faint">Remediation</h4>
                <p className="font-serif text-[15.5px] leading-relaxed text-ink">{sel.remediation}</p>
              </section>
            </div>
            <div className="sticky bottom-0 border-t border-rule bg-card p-6">
              <Button size="lg" className="w-full" disabled={sel.status === 'fixed'}>
                {sel.status === 'fixed' ? 'Marked as resolved' : 'Mark as resolved'}
              </Button>
            </div>
          </DrawerContent>
        )}
      </Drawer>
    </ClientShell>
  )
}
