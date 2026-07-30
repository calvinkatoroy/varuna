import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Shield, Bell, Filter, Lock, Check, X as XIcon, ArrowRight, ArrowLeft, Download,
  Upload, FileText, KeyRound, Activity, Plus, Eye, LogOut, ChevronDown, Pause, Play,
} from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
import { Drawer, DrawerContent, DrawerTitle, DrawerClose } from '@/components/ui/drawer'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { AdvancedScanDrawer } from './AdvancedScanDrawer'
import { useLiquidGlassAll } from '@/lib/useLiquidGlass'
import { revealTiles } from '@/lib/motion'
import { toast } from '@/lib/toast'

type Card = {
  id: string; client: string; target: string; mode: string
  sev: { c: number; h: number; m: number; l: number }; meta: string; owner?: string; suspended?: boolean
}
type Col = { id: string; title: string; accent: string; cards: Card[] }

const dot: Record<string, string> = {
  accent: 'bg-accent', info: 'bg-info', high: 'bg-high', crit: 'bg-crit', med: 'bg-med', low: 'bg-low',
}
const STAGES = ['pending', 'scanning', 'in_review_reporter', 'in_review_lead', 'in_review_governance', 'delivered']
const stageName: Record<string, string> = {
  pending: 'Pending', scanning: 'Scanning', in_review_reporter: 'Reporter',
  in_review_lead: 'Lead', in_review_governance: 'Governance', delivered: 'Delivered',
}
const isReview = (s: string) => s.startsWith('in_review')
const sevChip = (n: number, cls: string, letter: string) =>
  n > 0 ? <span className={`rounded-md px-1.5 py-0.5 text-[10.5px] font-bold ${cls}`}>{n}{letter}</span> : null

const ctrl = 'grid h-11 w-11 place-items-center rounded-full bg-white/10 text-[#F2F5EF] backdrop-blur-md transition-colors hover:bg-white/[.18]'
const sampleVersions = [
  { n: 1, editor: 'system', note: 'auto-generated v1', when: 'Jun 19, 09:12' },
  { n: 2, editor: 'Aisah', note: 'fixed exec summary · 2 FPs marked', when: 'Jun 19, 14:40' },
]

export default function TeamBoard() {
  const [cols, setCols] = useState<Col[] | null>(null)
  const [sel, setSel] = useState<{ card: Card; col: string } | null>(null)
  const [open, setOpen] = useState(false)
  const [scanOpen, setScanOpen] = useState(false)
  const [client, setClient] = useState<string | null>(null)

  useEffect(() => { api.get('/api/pipeline/board').then(setCols) }, [])
  useEffect(() => { if (cols) revealTiles('.pcard') }, [cols, client])
  useLiquidGlassAll('.pcard', { scale: -40, blur: 2, mapBlur: 7, saturate: 1.2, chroma: 0 }, [cols, client])

  const clients = useMemo(() => [...new Set((cols ?? []).flatMap((c) => c.cards.map((k) => k.client)))], [cols])
  const view = useMemo(
    () => (cols ?? []).map((c) => ({ ...c, cards: client ? c.cards.filter((k) => k.client === client) : c.cards })),
    [cols, client],
  )

  const move = (id: string, from: string, to: string, msg: string) => {
    setCols((cs) => {
      if (!cs) return cs
      const card = cs.find((c) => c.id === from)?.cards.find((k) => k.id === id)
      if (!card) return cs
      return cs.map((c) => (c.id === from ? { ...c, cards: c.cards.filter((k) => k.id !== id) } : c.id === to ? { ...c, cards: [card, ...c.cards] } : c))
    })
    toast(msg); setOpen(false)
  }
  const reject = (c: Card, col: string) => {
    setCols((cs) => cs?.map((x) => (x.id === col ? { ...x, cards: x.cards.filter((k) => k.id !== c.id) } : x)) ?? cs)
    toast(`Proposal rejected: ${c.client}.`); setOpen(false)
  }
  const forward = (c: Card, col: string) => { const to = STAGES[Math.min(STAGES.indexOf(col) + 1, STAGES.length - 1)]; move(c.id, col, to, `Forwarded to ${stageName[to]}.`) }
  const back = (c: Card, col: string) => { const to = STAGES[Math.max(STAGES.indexOf(col) - 1, 0)]; move(c.id, col, to, `Sent back to ${stageName[to]}.`) }
  const toggleSuspend = (c: Card, col: string) => {
    const next = !c.suspended
    setCols((cs) => cs?.map((x) => (x.id === col ? { ...x, cards: x.cards.map((k) => (k.id === c.id ? { ...k, suspended: next } : k)) } : x)) ?? cs)
    setSel((s) => (s && s.card.id === c.id ? { ...s, card: { ...s.card, suspended: next } } : s))
    toast(next ? `Scan suspended for ${c.client}.` : `Scan resumed for ${c.client}.`)
  }

  return (
    <div className="mx-auto max-w-[1500px] p-[clamp(10px,2vw,28px)]">
      {/* team header band */}
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
          <span className="rounded-pill bg-[#F4F6F1] px-3.5 py-1.5 text-[13px] font-semibold text-[#12140F]">Board</span>
          <Link to="/team/findings" className="rounded-pill px-3.5 py-1.5 text-[13px] font-medium text-[#F2F5EF]/70">Findings</Link>
        </div>
        <div>
          <div className="flex items-center gap-2 text-[12.5px] text-[#F2F5EF]/70"><Lock size={13} /> Private plane · Tailscale · Security team</div>
          <h1 className="text-[22px] font-bold tracking-[-0.02em]">Review Pipeline</h1>
        </div>
        <div className="ml-auto flex items-center gap-2.5">
          <button onClick={() => setScanOpen(true)} className="flex items-center gap-2 rounded-pill bg-[#F4F6F1] px-4 py-2.5 text-[13px] font-semibold text-[#12140F] transition-opacity hover:opacity-90">
            <Plus size={15} /> New scan
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-2 rounded-pill bg-white/10 px-4 py-2.5 text-[13px] font-medium text-[#F2F5EF] backdrop-blur-md">
              <Filter size={15} /> {client ?? 'All clients'} <ChevronDown size={14} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setClient(null)}>All clients</DropdownMenuItem>
              <DropdownMenuSeparator />
              {clients.map((cl) => <DropdownMenuItem key={cl} onClick={() => setClient(cl)}>{cl}</DropdownMenuItem>)}
            </DropdownMenuContent>
          </DropdownMenu>
          <ThemeToggle />
          <DropdownMenu>
            <DropdownMenuTrigger aria-label="Notifications" className={`relative ${ctrl}`}>
              <Bell size={18} />
              <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-accent ring-2 ring-[#0e211b]" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[280px]">
              <DropdownMenuLabel>Notifications</DropdownMenuLabel>
              <DropdownMenuItem className="items-start gap-2.5"><span className="mt-0.5 text-accent"><FileText size={15} /></span><span className="flex-1"><span className="block text-[13px] text-ink">New proposal: Nimbus Ltd</span><span className="text-[11.5px] text-ink-faint">2h ago</span></span></DropdownMenuItem>
              <DropdownMenuItem className="items-start gap-2.5"><span className="mt-0.5 text-info"><Activity size={15} /></span><span className="flex-1"><span className="block text-[13px] text-ink">Scan finished: Vault Bank</span><span className="text-[11.5px] text-ink-faint">Just now</span></span></DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger aria-label="Account" className="grid h-11 w-11 place-items-center rounded-full text-sm font-bold text-white" style={{ background: 'linear-gradient(160deg,#3fb98a,#268a63)' }}>RY</DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <div className="px-3 py-2"><div className="text-[14px] font-semibold text-ink">Riyan</div><div className="text-[12px] text-ink-muted">Lead pentester</div></div>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => location.assign('/')} className="text-crit"><LogOut size={15} /> Sign out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* kanban */}
      {!cols ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="mt-3.5 flex gap-3 overflow-x-auto p-1">
          {view.map((col) => (
            <div key={col.id} className="flex w-[280px] flex-none flex-col">
              <div className="mb-2.5 flex items-center gap-2 px-1">
                <span className={`h-2 w-2 rounded-full ${dot[col.accent]}`} />
                <h3 className="text-[13.5px] font-bold text-ink">{col.title}</h3>
                <span className="ml-auto rounded-pill bg-card px-2 py-0.5 text-[11.5px] font-semibold text-ink-muted">{col.cards.length}</span>
              </div>
              <div className="flex flex-col gap-2.5">
                {col.cards.map((c) => (
                  <DropdownMenu key={c.id}>
                    <DropdownMenuTrigger asChild>
                      <button style={{ opacity: 0 }} className="pcard glass-card liquid rounded-bento p-3.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-[13.5px] font-semibold text-ink">{c.client}</span>
                          <span className={`flex-none rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase ${c.mode === 'advanced' ? 'bg-accent-soft text-accent-ink' : 'bg-panel text-ink-muted'}`}>{c.mode}</span>
                        </div>
                        <div className="mono mt-0.5 truncate text-[12px] text-ink-muted">{c.target}</div>
                        <div className="mt-2.5 flex items-center gap-1.5">
                          {sevChip(c.sev.c, 'bg-crit-bg text-crit', 'C')}
                          {sevChip(c.sev.h, 'bg-high-bg text-high', 'H')}
                          {sevChip(c.sev.m, 'bg-med-bg text-med', 'M')}
                          {sevChip(c.sev.l, 'bg-low-bg text-low', 'L')}
                          {c.sev.c + c.sev.h + c.sev.m + c.sev.l === 0 && <span className="text-[11px] text-ink-faint">no findings yet</span>}
                        </div>
                        <div className="mt-2.5 flex items-center justify-between border-t border-rule pt-2.5">
                          <span className={`flex items-center gap-1.5 text-[11.5px] ${c.suspended ? 'font-semibold text-med' : 'text-ink-faint'}`}>
                            {c.suspended && <Pause size={11} />}
                            {c.suspended ? 'Suspended' : c.meta}
                          </span>
                          {c.owner && <span className="grid h-6 w-6 place-items-center rounded-full text-[10.5px] font-bold text-white" style={{ background: 'linear-gradient(160deg,#f4996d,#F26A43)' }}>{c.owner[0]}</span>}
                        </div>
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuLabel>{col.title}</DropdownMenuLabel>
                      {col.id === 'pending' && (
                        <>
                          <DropdownMenuItem onClick={() => move(c.id, col.id, 'scanning', `Approved. Scan queued for ${c.client}.`)} className="text-low focus:bg-low-bg"><Check size={15} /> Approve proposal</DropdownMenuItem>
                          <DropdownMenuItem onClick={() => reject(c, col.id)} className="text-crit focus:bg-crit-bg"><XIcon size={15} /> Reject</DropdownMenuItem>
                        </>
                      )}
                      {col.id === 'scanning' && (
                        <DropdownMenuItem onClick={() => toggleSuspend(c, col.id)} className={c.suspended ? 'text-low focus:bg-low-bg' : 'text-med focus:bg-med-bg'}>
                          {c.suspended ? <><Play size={15} /> Resume scan</> : <><Pause size={15} /> Suspend scan</>}
                        </DropdownMenuItem>
                      )}
                      {isReview(col.id) && (
                        <>
                          <DropdownMenuItem onClick={() => forward(c, col.id)}><ArrowRight size={15} /> Forward stage</DropdownMenuItem>
                          <DropdownMenuItem onClick={() => back(c, col.id)}><ArrowLeft size={15} /> Send back</DropdownMenuItem>
                        </>
                      )}
                      {col.id === 'delivered' && <DropdownMenuItem onClick={() => { toast(`New view-once password issued for ${c.client}.`) }}><KeyRound size={15} /> Re-issue password</DropdownMenuItem>}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => { setSel({ card: c, col: col.id }); setOpen(true) }}><Eye size={15} /> View details</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                ))}
                {col.cards.length === 0 && <div className="rounded-bento border border-dashed border-rule px-3.5 py-6 text-center text-[12px] text-ink-faint">Nothing here</div>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* review drawer */}
      <Drawer open={open} onOpenChange={setOpen}>
        {sel && (
          <DrawerContent>
            <div className="border-b border-rule p-6">
              <span className="text-[12px] font-medium text-ink-muted">{sel.card.mode === 'advanced' ? 'Advanced' : 'Standard'} engagement · {stageName[sel.col]}</span>
              <DrawerTitle className="mt-1 text-[20px] font-bold tracking-[-0.02em] text-ink">{sel.card.client}</DrawerTitle>
              <div className="mono text-[13px] text-ink-muted">{sel.card.target}</div>
            </div>

            <div className="flex-1 space-y-6 p-6">
              <section>
                <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Proposal</h4>
                <div className="grid grid-cols-2 gap-3 text-[13px]">
                  <div><div className="text-ink-muted">Purpose</div><div className="font-semibold text-ink">Pre-release</div></div>
                  <div><div className="text-ink-muted">Division</div><div className="font-semibold text-ink">Engineering</div></div>
                  <div><div className="text-ink-muted">Environment</div><div className="font-semibold text-ink">Production</div></div>
                  <div><div className="text-ink-muted">Authorization</div><div className="flex items-center gap-1 font-semibold text-low"><Check size={14} /> Attested</div></div>
                </div>
              </section>

              {isReview(sel.col) && (
                <section>
                  <div className="mb-2.5 flex items-center justify-between">
                    <h4 className="text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Versions</h4>
                    <button onClick={() => toast('Upload a new .docx version')} className="flex items-center gap-1.5 text-[12px] font-semibold text-accent hover:opacity-80"><Upload size={13} /> Upload new</button>
                  </div>
                  <ul className="space-y-2">
                    {sampleVersions.map((v) => (
                      <li key={v.n} className="flex items-center gap-3 rounded-input border border-rule bg-panel p-3">
                        <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-card text-[12px] font-bold text-ink">v{v.n}</span>
                        <div className="min-w-0 flex-1"><div className="truncate text-[13px] font-medium text-ink">{v.note}</div><div className="text-[11.5px] text-ink-faint">{v.editor} · {v.when}</div></div>
                        <button onClick={() => toast(`Downloading v${v.n}.docx`)} aria-label="Download" className="grid h-8 w-8 flex-none place-items-center rounded-full text-ink-muted hover:bg-card hover:text-ink"><Download size={15} /></button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {sel.col === 'scanning' && (
                <section className="flex items-center gap-3 rounded-input border border-rule bg-panel p-4 text-[13px]">
                  {sel.card.suspended
                    ? <><Pause size={18} className="text-med" /> Scan suspended. Resume to continue where it left off.</>
                    : <><Activity size={18} className="text-info" /> Live scan in progress. Nuclei 62%. Findings stream in as tools finish.</>}
                </section>
              )}

              {sel.col === 'delivered' && (
                <section>
                  <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Delivery</h4>
                  <div className="flex items-center gap-3 rounded-input border border-rule bg-panel p-3.5 text-[13px]"><FileText size={18} className="text-accent" /> Protected PDF sent · view-once password.</div>
                </section>
              )}
            </div>

            <div className="sticky bottom-0 flex gap-2.5 border-t border-rule bg-card p-6">
              {sel.col === 'pending' && (
                <>
                  <Button variant="outline" size="lg" className="flex-1" onClick={() => reject(sel.card, sel.col)}><XIcon size={16} /> Reject</Button>
                  <Button size="lg" className="flex-1" onClick={() => move(sel.card.id, sel.col, 'scanning', `Approved. Scan queued for ${sel.card.client}.`)}><Check size={16} /> Approve</Button>
                </>
              )}
              {isReview(sel.col) && (
                <>
                  <Button variant="outline" size="lg" className="flex-1" onClick={() => back(sel.card, sel.col)}><ArrowLeft size={16} /> Send back</Button>
                  <Button size="lg" className="flex-1" onClick={() => forward(sel.card, sel.col)}>Forward <ArrowRight size={16} /></Button>
                </>
              )}
              {sel.col === 'delivered' && (
                <Button variant="outline" size="lg" className="w-full" onClick={() => { toast(`New view-once password issued for ${sel.card.client}.`); setOpen(false) }}><KeyRound size={16} /> Re-issue password</Button>
              )}
              {sel.col === 'scanning' && (
                <>
                  <Button variant="outline" size="lg" className="flex-1" onClick={() => toggleSuspend(sel.card, sel.col)}>
                    {sel.card.suspended ? <><Play size={16} /> Resume scan</> : <><Pause size={16} /> Suspend scan</>}
                  </Button>
                  <DrawerClose asChild><Button size="lg" className="flex-1">Close</Button></DrawerClose>
                </>
              )}
            </div>
          </DrawerContent>
        )}
      </Drawer>
      <AdvancedScanDrawer open={scanOpen} onOpenChange={setScanOpen} onLaunch={(t) => toast(`Scan launched: ${t}`)} />
    </div>
  )
}
