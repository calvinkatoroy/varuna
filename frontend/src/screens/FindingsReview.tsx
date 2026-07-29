import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Shield, ArrowLeft, Filter, ShieldCheck, Bug, FlaskConical } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'

type F = {
  id: string; name: string; severity: string; asset: string; tool: string
  cve: string; verdict: 'tp' | 'fp'; status: string; evidence: string; remediation: string
}

const sevPill: Record<string, string> = {
  critical: 'bg-crit-bg text-crit', high: 'bg-high-bg text-high', medium: 'bg-med-bg text-med', low: 'bg-low-bg text-low',
}
const sevDot: Record<string, string> = { critical: 'bg-crit', high: 'bg-high', medium: 'bg-med', low: 'bg-low' }
const statusPill: Record<string, string> = {
  open: 'bg-accent-soft text-accent-ink', fixed: 'bg-low-bg text-low', accepted: 'bg-panel text-ink-muted',
}

export default function FindingsReview() {
  const [rows, setRows] = useState<F[] | null>(null)
  const [sel, setSel] = useState<F | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    api.get('/api/findings').then(setRows)
  }, [])

  return (
    <div className="mx-auto max-w-[1300px] p-[clamp(10px,2vw,28px)]">
      <header
        className="relative flex flex-wrap items-center gap-4 overflow-hidden rounded-bento-lg px-[clamp(18px,2.4vw,30px)] py-5 text-[#F2F5EF]"
        style={{ background: 'radial-gradient(120% 140% at 88% -20%, rgba(242,106,67,.24), transparent 46%), linear-gradient(158deg,#123c33 0%,#0e211b 55%,#070908 100%)' }}
      >
        <div className="flex items-center gap-2.5 text-[20px] font-bold tracking-[-0.02em]">
          <span className="grid h-8 w-8 place-items-center rounded-[10px]" style={{ background: 'conic-gradient(from 210deg,#F26A43,#f4996d,#F26A43)', boxShadow: 'inset 0 0 0 2px rgba(255,255,255,.16)' }}>
            <Shield size={17} className="fill-white text-white" />
          </span>
          Varuna
        </div>
        <div className="hidden h-6 w-px bg-white/15 sm:block" />
        <div className="flex items-center gap-1 rounded-pill bg-white/10 p-1 backdrop-blur-md">
          <Link to="/team" className="rounded-pill px-3.5 py-1.5 text-[13px] font-medium text-[#F2F5EF]/70">Board</Link>
          <span className="rounded-pill bg-[#F4F6F1] px-3.5 py-1.5 text-[13px] font-semibold text-[#12140F]">Findings</span>
        </div>
        <div>
          <div className="text-[12.5px] text-[#F2F5EF]/70">Acme Corp · acme.io</div>
          <h1 className="text-[22px] font-bold tracking-[-0.02em]">Findings review</h1>
        </div>
        <div className="ml-auto flex items-center gap-2.5">
          <button className="flex items-center gap-2 rounded-pill bg-white/10 px-4 py-2.5 text-[13px] font-medium backdrop-blur-md"><Filter size={15} /> All severities</button>
          <ThemeToggle />
        </div>
      </header>

      {!rows ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="mt-3.5 overflow-hidden rounded-bento-lg border border-rule bg-card">
          <div className="grid grid-cols-[auto_1fr_auto] gap-4 border-b border-rule px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint sm:grid-cols-[90px_1fr_1fr_90px_90px]">
            <span>Severity</span><span>Finding</span><span className="hidden sm:block">Asset</span><span className="hidden sm:block">Verdict</span><span className="text-right sm:text-left">Status</span>
          </div>
          {rows.map((f) => (
            <button
              key={f.id}
              onClick={() => { setSel(f); setOpen(true) }}
              className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-rule px-5 py-3.5 text-left transition-colors last:border-0 hover:bg-panel sm:grid-cols-[90px_1fr_1fr_90px_90px]"
            >
              <span className={`inline-flex items-center gap-1.5 justify-self-start rounded-md px-2 py-1 text-[11px] font-bold capitalize ${sevPill[f.severity]}`}><span className={`h-1.5 w-1.5 rounded-full ${sevDot[f.severity]}`} />{f.severity}</span>
              <span className="min-w-0"><span className="block truncate text-[14px] font-semibold text-ink">{f.name}</span><span className="text-[11.5px] text-ink-faint">{f.tool} · {f.cve}</span></span>
              <span className="hidden truncate font-mono text-[12px] text-ink-muted sm:block">{f.asset}</span>
              <span className={`hidden text-[11px] font-bold uppercase sm:block ${f.verdict === 'tp' ? 'text-low' : 'text-ink-faint'}`}>{f.verdict === 'tp' ? '● TP' : '○ FP'}</span>
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
                <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Verdict</h4>
                <div className="grid grid-cols-2 gap-2">
                  <VerdictBtn on={sel.verdict === 'tp'} icon={<Bug size={15} />} label="True positive" tone="low" />
                  <VerdictBtn on={sel.verdict === 'fp'} icon={<FlaskConical size={15} />} label="False positive" tone="faint" />
                </div>
              </section>
              <section>
                <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Evidence</h4>
                <pre className="overflow-x-auto rounded-input border border-rule bg-panel p-3 font-mono text-[12px] leading-relaxed text-ink">{sel.evidence}</pre>
              </section>
              <section>
                <h4 className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint"><ShieldCheck size={13} className="text-accent" /> AI remediation</h4>
                <p className="text-[13.5px] leading-relaxed text-ink">{sel.remediation}</p>
              </section>
            </div>

            <div className="sticky bottom-0 flex gap-2.5 border-t border-rule bg-card p-6">
              <Button variant="outline" size="lg" className="flex-1">Mark fixed</Button>
              <Button size="lg" className="flex-1">Save</Button>
            </div>
          </DrawerContent>
        )}
      </Drawer>
    </div>
  )
}

function VerdictBtn({ on, icon, label, tone }: { on: boolean; icon: React.ReactNode; label: string; tone: string }) {
  return (
    <button className={`flex items-center justify-center gap-2 rounded-input border px-3 py-3 text-[13px] font-semibold transition-colors ${on ? (tone === 'low' ? 'border-low bg-low-bg text-low' : 'border-rule bg-panel text-ink') : 'border-rule text-ink-muted hover:text-ink'}`}>
      {icon} {label}
    </button>
  )
}
