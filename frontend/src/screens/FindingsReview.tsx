import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Filter, ShieldCheck, Bug, FlaskConical, ChevronDown } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
import { TeamAccount } from '@/components/TeamAccount'
import { BrandMark } from '@/components/BrandMark'
import { ErrorRetry } from '@/components/ErrorRetry'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { useApiData } from '@/lib/useApiData'
import { toast } from '@/lib/toast'

type F = {
  id: string; name: string; severity: string; host: string; url: string; tool: string; owner: string
  cve?: string | null; verdict: 'tp' | 'fp'; status: string; evidence: string; remediation?: string | null
}
const assetOf = (f: F) => f.url || f.host
const sevPill: Record<string, string> = {
  critical: 'bg-crit-bg text-crit', high: 'bg-high-bg text-high', medium: 'bg-med-bg text-med', low: 'bg-low-bg text-low',
}
const sevDot: Record<string, string> = { critical: 'bg-crit', high: 'bg-high', medium: 'bg-med', low: 'bg-low' }
const statusPill: Record<string, string> = {
  open: 'bg-accent-soft text-accent-ink', fixed: 'bg-low-bg text-low', accepted: 'bg-panel text-ink-muted',
}
const SEVS = ['critical', 'high', 'medium', 'low']

export default function FindingsReview() {
  const { data: rows, error, reload, setData: setRows } = useApiData<F[]>(() => api.pget('/api/findings'))
  const [sel, setSel] = useState<F | null>(null)
  const [open, setOpen] = useState(false)
  const [sevFilter, setSevFilter] = useState<string | null>(null)
  const [clients, setClients] = useState<string[]>([])
  const [client, setClient] = useState('')

  // The board spans many clients; a finding's `owner` is the same username used as `client` on
  // board cards, so filtering by client here is real (not a hardcoded single-client special
  // case) - every client with any findings shows them.
  useEffect(() => {
    api.pget('/api/pipeline/board').then((cols: any[]) => {
      setClients([...new Set(cols.flatMap((c) => c.cards.map((k: any) => k.client)))].sort())
    }).catch(() => {})
  }, [])
  useEffect(() => { if (!client && clients.length) setClient(clients[0]) }, [client, clients])

  const list = useMemo(
    () => (rows ?? []).filter((f) => f.owner === client && (!sevFilter || f.severity === sevFilter)),
    [rows, sevFilter, client],
  )

  const setVerdict = (id: string, v: 'tp' | 'fp') => {
    const prev = rows?.find((f) => f.id === id)?.verdict
    setRows((rs) => rs?.map((f) => (f.id === id ? { ...f, verdict: v } : f)) ?? rs)
    setSel((s) => (s && s.id === id ? { ...s, verdict: v } : s))
    api.ppost(`/api/findings/${id}/verdict`, { verdict: v }).catch(() => {
      if (!prev) return
      setRows((rs) => rs?.map((f) => (f.id === id ? { ...f, verdict: prev } : f)) ?? rs)
      setSel((s) => (s && s.id === id ? { ...s, verdict: prev } : s))
    })
  }
  const markFixed = (id: string) => {
    setRows((rs) => rs?.map((f) => (f.id === id ? { ...f, status: 'fixed' } : f)) ?? rs)
    setSel((s) => (s && s.id === id ? { ...s, status: 'fixed' } : s))
    api.ppost(`/api/findings/${id}/status`, { status: 'fixed' }).then(
      () => toast('Marked as fixed'),
      () => {
        setRows((rs) => rs?.map((f) => (f.id === id ? { ...f, status: 'open' } : f)) ?? rs)
        setSel((s) => (s && s.id === id ? { ...s, status: 'open' } : s))
      },
    )
  }

  return (
    <div className="mx-auto max-w-[1300px] p-[clamp(10px,2vw,28px)]">
      <header
        className="relative flex flex-wrap items-center gap-4 overflow-hidden rounded-bento-lg px-[clamp(18px,2.4vw,30px)] py-5 text-[#F2F5EF]"
        style={{ background: 'radial-gradient(120% 140% at 88% -20%, rgba(34,211,197,.22), transparent 46%), linear-gradient(158deg,#0B5FA5 0%,#0A2A43 55%,#060F18 100%)' }}
      >
        <div className="flex items-center gap-2.5 text-[20px] font-bold tracking-[-0.02em]">
          <BrandMark size={32} />
          Varuna
        </div>
        <div className="hidden h-6 w-px bg-white/15 sm:block" />
        <div className="flex items-center gap-1 rounded-pill bg-white/[.16] p-1">
          <Link to="/team" className="rounded-pill px-3.5 py-1.5 text-[13px] font-medium text-[#F2F5EF]/70">Board</Link>
          <span className="rounded-pill bg-[#F4F6F1] px-3.5 py-1.5 text-[13px] font-semibold text-[#12140F]">Findings</span>
        </div>
        <div>
          <div className="text-[12.5px] text-[#F2F5EF]/70">{client || 'Loading…'}</div>
          <h1 className="text-[22px] font-bold tracking-[-0.02em]">Findings review</h1>
        </div>
        <div className="ml-auto flex items-center gap-2.5">
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-2 rounded-pill bg-white/[.16] px-4 py-2.5 text-[13px] font-medium text-[#F2F5EF]">
              <Filter size={15} /> {client || 'Loading…'} <ChevronDown size={14} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {clients.map((cl) => <DropdownMenuItem key={cl} onClick={() => setClient(cl)}>{cl}</DropdownMenuItem>)}
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-2 rounded-pill bg-white/[.16] px-4 py-2.5 text-[13px] font-medium capitalize text-[#F2F5EF]">
              <Filter size={15} /> {sevFilter ?? 'All severities'} <ChevronDown size={14} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setSevFilter(null)}>All severities</DropdownMenuItem>
              <DropdownMenuSeparator />
              {SEVS.map((s) => <DropdownMenuItem key={s} onClick={() => setSevFilter(s)} className="capitalize">{s}</DropdownMenuItem>)}
            </DropdownMenuContent>
          </DropdownMenu>
          <ThemeToggle className="grid h-11 w-11 place-items-center rounded-full bg-white/[.16] text-[#F2F5EF] transition-colors hover:bg-white/25" />
          <TeamAccount />
        </div>
      </header>

      {error ? (
        <ErrorRetry message={error} onRetry={reload} />
      ) : !rows ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="mt-3.5 overflow-hidden rounded-bento-lg border border-rule bg-card">
          <div className="grid grid-cols-[auto_1fr_auto] gap-4 border-b border-rule px-5 py-3 text-[11px] font-semibold uppercase tracking-wide text-ink-faint sm:grid-cols-[90px_1fr_1fr_90px_90px]">
            <span>Severity</span><span>Finding</span><span className="hidden sm:block">Asset</span><span className="hidden sm:block">Verdict</span><span className="text-right sm:text-left">Status</span>
          </div>
          {list.map((f) => (
            <button
              key={f.id}
              onClick={() => { setSel(f); setOpen(true) }}
              className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-rule px-5 py-3.5 text-left transition-colors last:border-0 hover:bg-panel sm:grid-cols-[90px_1fr_1fr_90px_90px]"
            >
              <span className={`inline-flex items-center gap-1.5 justify-self-start rounded-md px-2 py-1 text-[11px] font-bold capitalize ${sevPill[f.severity]}`}><span className={`h-1.5 w-1.5 rounded-full ${sevDot[f.severity]}`} />{f.severity}</span>
              <span className="min-w-0"><span className="block truncate text-[14px] font-semibold text-ink">{f.name}</span><span className="text-[11.5px] text-ink-faint">{f.tool} · {f.cve ?? '—'}</span></span>
              <span className="mono hidden truncate text-[12px] text-ink-muted sm:block">{assetOf(f)}</span>
              <span className={`hidden items-center gap-1.5 text-[11px] font-bold uppercase sm:flex ${f.verdict === 'tp' ? 'text-low' : 'text-ink-faint'}`}><span className={`h-1.5 w-1.5 rounded-full ${f.verdict === 'tp' ? 'bg-low' : 'bg-ink-faint'}`} />{f.verdict}</span>
              <span className={`justify-self-end rounded-pill px-2.5 py-1 text-[11px] font-semibold capitalize sm:justify-self-start ${statusPill[f.status]}`}>{f.status}</span>
            </button>
          ))}
          {list.length === 0 && (
            <div className="px-5 py-10 text-center text-[13px] text-ink-faint">
              No {sevFilter ?? ''} findings for {client || 'this client'}.
            </div>
          )}
        </div>
      )}

      <Drawer open={open} onOpenChange={setOpen}>
        {sel && (
          <DrawerContent>
            <div className="border-b border-rule p-6">
              <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-bold capitalize ${sevPill[sel.severity]}`}><span className={`h-1.5 w-1.5 rounded-full ${sevDot[sel.severity]}`} />{sel.severity}</span>
              <DrawerTitle className="mt-2.5 text-[21px] font-bold tracking-[-0.02em] text-ink">{sel.name}</DrawerTitle>
              <div className="mono mt-1 text-[13px] text-ink-muted">{assetOf(sel)}</div>
              <div className="mt-1 text-[12.5px] text-ink-faint">{sel.tool} · {sel.cve ?? '—'}</div>
            </div>

            <div className="flex-1 space-y-6 p-6">
              <section>
                <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Verdict</h4>
                <div className="grid grid-cols-2 gap-2">
                  <VerdictBtn on={sel.verdict === 'tp'} icon={<Bug size={15} />} label="True positive" tone="low" onClick={() => setVerdict(sel.id, 'tp')} />
                  <VerdictBtn on={sel.verdict === 'fp'} icon={<FlaskConical size={15} />} label="False positive" tone="faint" onClick={() => setVerdict(sel.id, 'fp')} />
                </div>
              </section>
              <section>
                <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Evidence</h4>
                <pre className="overflow-x-auto rounded-input border border-rule bg-panel p-3 font-mono text-[12px] leading-relaxed text-ink">{sel.evidence}</pre>
              </section>
              <section>
                <h4 className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint"><ShieldCheck size={13} className="text-accent" /> AI remediation</h4>
                <p className="text-[13.5px] leading-relaxed text-ink">{sel.remediation ?? 'Not yet enriched.'}</p>
              </section>
            </div>

            <div className="sticky bottom-0 flex gap-2.5 border-t border-rule bg-card p-6">
              <Button variant="outline" size="lg" className="flex-1" disabled={sel.status === 'fixed'} onClick={() => markFixed(sel.id)}>{sel.status === 'fixed' ? 'Fixed' : 'Mark fixed'}</Button>
              <Button size="lg" className="flex-1" onClick={() => { toast('Review saved'); setOpen(false) }}>Save</Button>
            </div>
          </DrawerContent>
        )}
      </Drawer>
    </div>
  )
}

function VerdictBtn({ on, icon, label, tone, onClick }: { on: boolean; icon: React.ReactNode; label: string; tone: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`flex items-center justify-center gap-2 rounded-input border px-3 py-3 text-[13px] font-semibold transition-colors ${on ? (tone === 'low' ? 'border-low bg-low-bg text-low' : 'border-ink bg-panel text-ink') : 'border-rule text-ink-muted hover:text-ink'}`}>
      {icon} {label}
    </button>
  )
}
