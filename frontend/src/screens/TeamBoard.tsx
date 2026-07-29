import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Shield, Bell, Filter, Lock, Check, X as XIcon, ArrowRight, ArrowLeft, Download,
  Upload, FileText, KeyRound, Activity, Plus, Eye,
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
import { revealTiles } from '@/lib/motion'

type Card = {
  id: string; client: string; target: string; mode: string
  sev: { c: number; h: number; m: number; l: number }; meta: string; owner?: string
}
type Col = { id: string; title: string; accent: string; cards: Card[] }

const dot: Record<string, string> = {
  accent: 'bg-accent', info: 'bg-info', high: 'bg-high', crit: 'bg-crit', med: 'bg-med', low: 'bg-low',
}
const sevChip = (n: number, cls: string, letter: string) =>
  n > 0 ? (
    <span className={`rounded-md px-1.5 py-0.5 text-[10.5px] font-bold ${cls}`}>{n}{letter}</span>
  ) : null

const stageActions: Record<string, string> = {
  pending: 'approve', scanning: 'scan', in_review_reporter: 'review',
  in_review_lead: 'review', in_review_governance: 'review', delivered: 'delivered',
}
const sampleVersions = [
  { n: 1, editor: 'system', note: 'auto-generated v1', when: 'Jun 19, 09:12' },
  { n: 2, editor: 'Aisah', note: 'fixed exec summary · 2 FPs marked', when: 'Jun 19, 14:40' },
]

export default function TeamBoard() {
  const [cols, setCols] = useState<Col[] | null>(null)
  const [sel, setSel] = useState<Card | null>(null)
  const [open, setOpen] = useState(false)
  const [scanOpen, setScanOpen] = useState(false)

  useEffect(() => {
    api.get('/api/pipeline/board').then(setCols)
  }, [])
  useEffect(() => {
    if (cols) revealTiles('.pcard')
  }, [cols])

  function openCard(c: Card) {
    setSel(c)
    setOpen(true)
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
          <div className="flex items-center gap-2 text-[12.5px] text-[#F2F5EF]/70">
            <Lock size={13} /> Private plane · Tailscale · Security team
          </div>
          <h1 className="text-[22px] font-bold tracking-[-0.02em]">Review Pipeline</h1>
        </div>
        <div className="ml-auto flex items-center gap-2.5">
          <button onClick={() => setScanOpen(true)} className="flex items-center gap-2 rounded-pill bg-[#F4F6F1] px-4 py-2.5 text-[13px] font-semibold text-[#12140F] transition-opacity hover:opacity-90">
            <Plus size={15} /> New scan
          </button>
          <button className="flex items-center gap-2 rounded-pill bg-white/10 px-4 py-2.5 text-[13px] font-medium backdrop-blur-md">
            <Filter size={15} /> All clients
          </button>
          <ThemeToggle />
          <button aria-label="Notifications" className="grid h-11 w-11 place-items-center rounded-full bg-white/10 backdrop-blur-md"><Bell size={18} /></button>
          <button aria-label="Account" className="grid h-11 w-11 place-items-center rounded-full text-sm font-bold text-white" style={{ background: 'linear-gradient(160deg,#3fb98a,#268a63)' }}>RY</button>
        </div>
      </header>

      {/* kanban */}
      {!cols ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="mt-3.5 flex gap-3 overflow-x-auto rounded-bento-lg bg-panel p-3.5">
          {cols.map((col) => (
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
                      <button
                        style={{ opacity: 0 }}
                        className="pcard rounded-bento border border-rule bg-card p-3.5 text-left shadow-sm transition-shadow hover:shadow-[0_10px_28px_rgba(0,0,0,.18)] focus:outline-none focus-visible:ring-2 focus-visible:ring-focus data-[state=open]:shadow-[0_10px_28px_rgba(0,0,0,.18)]"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="truncate text-[13.5px] font-semibold text-ink">{c.client}</span>
                          <span className={`flex-none rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase ${c.mode === 'advanced' ? 'bg-accent-soft text-accent-ink' : 'bg-panel text-ink-muted'}`}>{c.mode}</span>
                        </div>
                        <div className="mt-0.5 truncate text-[12px] text-ink-muted">{c.target}</div>
                        <div className="mt-2.5 flex items-center gap-1.5">
                          {sevChip(c.sev.c, 'bg-crit-bg text-crit', 'C')}
                          {sevChip(c.sev.h, 'bg-high-bg text-high', 'H')}
                          {sevChip(c.sev.m, 'bg-med-bg text-med', 'M')}
                          {sevChip(c.sev.l, 'bg-low-bg text-low', 'L')}
                          {c.sev.c + c.sev.h + c.sev.m + c.sev.l === 0 && <span className="text-[11px] text-ink-faint">no findings yet</span>}
                        </div>
                        <div className="mt-2.5 flex items-center justify-between border-t border-rule pt-2.5">
                          <span className="text-[11.5px] text-ink-faint">{c.meta}</span>
                          {c.owner && <span className="grid h-6 w-6 place-items-center rounded-full text-[10.5px] font-bold text-white" style={{ background: 'linear-gradient(160deg,#f4996d,#F26A43)' }}>{c.owner[0]}</span>}
                        </div>
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuLabel>{col.title}</DropdownMenuLabel>
                      {detectStage(c) === 'pending' && (
                        <>
                          <DropdownMenuItem className="text-low focus:bg-low-bg"><Check size={15} /> Approve proposal</DropdownMenuItem>
                          <DropdownMenuItem className="text-crit focus:bg-crit-bg"><XIcon size={15} /> Reject</DropdownMenuItem>
                        </>
                      )}
                      {stageActions[detectStage(c)] === 'review' && (
                        <>
                          <DropdownMenuItem><ArrowRight size={15} /> Forward stage</DropdownMenuItem>
                          <DropdownMenuItem><ArrowLeft size={15} /> Send back</DropdownMenuItem>
                        </>
                      )}
                      {detectStage(c) === 'delivered' && <DropdownMenuItem><KeyRound size={15} /> Re-issue password</DropdownMenuItem>}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => openCard(c)}><Eye size={15} /> View details</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                ))}
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
              <span className="text-[12px] font-medium text-ink-muted">{sel.mode === 'advanced' ? 'Advanced' : 'Standard'} engagement</span>
              <DrawerTitle className="mt-1 text-[20px] font-bold tracking-[-0.02em] text-ink">{sel.client}</DrawerTitle>
              <div className="text-[13px] text-ink-muted">{sel.target}</div>
            </div>

            <div className="flex-1 space-y-6 p-6">
              {/* proposal summary */}
              <section>
                <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Proposal</h4>
                <div className="grid grid-cols-2 gap-3 text-[13px]">
                  <div><div className="text-ink-muted">Purpose</div><div className="font-semibold text-ink">Pre-release</div></div>
                  <div><div className="text-ink-muted">Division</div><div className="font-semibold text-ink">Engineering</div></div>
                  <div><div className="text-ink-muted">Environment</div><div className="font-semibold text-ink">Production</div></div>
                  <div><div className="text-ink-muted">Authorization</div><div className="flex items-center gap-1 font-semibold text-low"><Check size={14} /> Attested</div></div>
                </div>
              </section>

              {/* stage-specific body */}
              {stageActions[detectStage(sel)] === 'review' && (
                <section>
                  <div className="mb-2.5 flex items-center justify-between">
                    <h4 className="text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Versions</h4>
                    <button className="flex items-center gap-1.5 text-[12px] font-semibold text-accent hover:opacity-80"><Upload size={13} /> Upload new</button>
                  </div>
                  <ul className="space-y-2">
                    {sampleVersions.map((v) => (
                      <li key={v.n} className="flex items-center gap-3 rounded-input border border-rule bg-panel p-3">
                        <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-card text-[12px] font-bold text-ink">v{v.n}</span>
                        <div className="min-w-0 flex-1"><div className="truncate text-[13px] font-medium text-ink">{v.note}</div><div className="text-[11.5px] text-ink-faint">{v.editor} · {v.when}</div></div>
                        <button aria-label="Download" className="grid h-8 w-8 flex-none place-items-center rounded-full text-ink-muted hover:bg-card hover:text-ink"><Download size={15} /></button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {stageActions[detectStage(sel)] === 'scan' && (
                <section className="flex items-center gap-3 rounded-input border border-rule bg-panel p-4 text-[13px]">
                  <Activity size={18} className="text-info" /> Live scan in progress — Nuclei 62%. Findings stream in as tools finish.
                </section>
              )}

              {stageActions[detectStage(sel)] === 'delivered' && (
                <section>
                  <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Delivery</h4>
                  <div className="flex items-center gap-3 rounded-input border border-rule bg-panel p-3.5 text-[13px]">
                    <FileText size={18} className="text-accent" /> Protected PDF sent · view-once password.
                  </div>
                </section>
              )}
            </div>

            {/* stage actions */}
            <div className="sticky bottom-0 flex gap-2.5 border-t border-rule bg-card p-6">
              {detectStage(sel) === 'pending' && (
                <>
                  <Button variant="outline" size="lg" className="flex-1"><XIcon size={16} /> Reject</Button>
                  <Button size="lg" className="flex-1"><Check size={16} /> Approve</Button>
                </>
              )}
              {stageActions[detectStage(sel)] === 'review' && (
                <>
                  <Button variant="outline" size="lg" className="flex-1"><ArrowLeft size={16} /> Send back</Button>
                  <Button size="lg" className="flex-1">Forward <ArrowRight size={16} /></Button>
                </>
              )}
              {detectStage(sel) === 'delivered' && (
                <Button variant="outline" size="lg" className="w-full"><KeyRound size={16} /> Re-issue password</Button>
              )}
              {detectStage(sel) === 'scanning' && (
                <DrawerClose asChild><Button variant="outline" size="lg" className="w-full">Close</Button></DrawerClose>
              )}
            </div>
          </DrawerContent>
        )}
      </Drawer>
      <AdvancedScanDrawer open={scanOpen} onOpenChange={setScanOpen} />
    </div>
  )
}

// The card id prefix encodes its column in the mock; map it back to a stage.
function detectStage(c: Card): string {
  const p = c.id[0]
  return { p: 'pending', s: 'scanning', r: 'in_review_reporter', l: 'in_review_lead', g: 'in_review_governance', d: 'delivered' }[p] || 'pending'
}
