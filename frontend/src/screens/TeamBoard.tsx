import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bell, Filter, Lock, Check, X as XIcon, ArrowRight, ArrowLeft, Download,
  Upload, FileText, KeyRound, Activity, Plus, Eye, ChevronDown, Pause, Play,
} from 'lucide-react'
import { api, download, upload } from '@/api'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
import { TeamAccount } from '@/components/TeamAccount'
import { BrandMark } from '@/components/BrandMark'
import { Drawer, DrawerContent, DrawerTitle, DrawerClose } from '@/components/ui/drawer'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { AdvancedScanDrawer, toApiOpts, type ScanOpts } from './AdvancedScanDrawer'
import { ErrorRetry } from '@/components/ErrorRetry'
import { ScanProgress } from '@/components/ScanProgress'
import { useApiData } from '@/lib/useApiData'
import { revealTiles } from '@/lib/motion'
import { toast } from '@/lib/toast'

type Card = {
  id: string; client: string; target: string; mode: string
  sev: { c: number; h: number; m: number; l: number }; meta: string; owner?: string
  suspended?: boolean; rejectReason?: string; jobId?: string
}
type Col = { id: string; title: string; accent: string; cards: Card[] }

const dot: Record<string, string> = {
  accent: 'bg-accent', info: 'bg-info', high: 'bg-high', crit: 'bg-crit', med: 'bg-med', low: 'bg-low',
}
const STAGES = ['pending', 'scanning', 'in_review_reporter', 'in_review_lead', 'in_review_governance', 'delivered']
const stageName: Record<string, string> = {
  pending: 'Pending', scanning: 'Scanning', in_review_reporter: 'Reporter',
  in_review_lead: 'Lead', in_review_governance: 'Governance', delivered: 'Delivered', rejected: 'Rejected',
}
const isReview = (s: string) => s.startsWith('in_review')
type Version = { version_no: number; editor: string; note: string; created_at: string }
// SQLite's datetime('now') comes back as "YYYY-MM-DD HH:MM:SS" (UTC, no offset) - not directly
// Date-parseable in every engine, and not the relative-friendly style used elsewhere here.
const whenOf = (sqliteTs: string) => new Date(sqliteTs.replace(' ', 'T') + 'Z').toLocaleString()
type Detail = { proposal: { purpose: string; division: string; environment: string; authorized: boolean }; versions?: Version[] }
const sevChip = (n: number, cls: string, letter: string) =>
  n > 0 ? <span className={`rounded-md px-1.5 py-0.5 text-[10.5px] font-bold ${cls}`}>{n}{letter}</span> : null

// No backdrop-filter: this header packs 6 controls in one row, and stacking that many blurred
// regions this close together triggers a real Chromium compositor bleed (see ClientTopbar).
const ctrl = 'grid h-11 w-11 place-items-center rounded-full bg-white/[.16] text-[#F2F5EF] transition-colors hover:bg-white/25'

export default function TeamBoard() {
  const { data: cols, error, reload: refetchBoard, setData: setCols } = useApiData<Col[]>(() => api.pget('/api/pipeline/board'))
  const [sel, setSel] = useState<{ card: Card; col: string } | null>(null)
  const [open, setOpen] = useState(false)
  const [scanOpen, setScanOpen] = useState(false)
  const [client, setClient] = useState<string | null>(null)
  const [detail, setDetail] = useState<Detail | null>(null)
  const [rejectNote, setRejectNote] = useState('')

  // Reveal only on first load / filter change: keying on `cols` replayed the fade-in (a visible
  // blank flash of the whole board) after every approve and on every 8s poll.
  const loaded = !!cols
  useEffect(() => { if (loaded) revealTiles('.pcard') }, [loaded, client])
  // Passive live-update: nothing else pushes scan progress/report stage changes to this page,
  // so without this the board is a snapshot from whenever it first loaded - a scan finishing
  // or another reviewer forwarding a report would never appear until a manual reload. Only
  // polls while something's actually in motion; stops once everything's pending/idle.
  useEffect(() => {
    const active = cols?.some((c) => c.id !== 'delivered' && c.id !== 'rejected' && c.cards.length > 0)
    if (!active) return
    const id = setInterval(refetchBoard, 8000)
    return () => clearInterval(id)
  }, [cols, refetchBoard])
  const reloadDetail = () => { if (sel) api.pget(`/api/pipeline/detail/${sel.card.id}`).then(setDetail).catch(() => setDetail(null)) }
  useEffect(() => {
    setRejectNote('')
    if (!sel) { setDetail(null); return }
    reloadDetail()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sel])
  // Reviewers download the .docx, edit it in Word, and upload it back as the next version; or
  // regenerate the whole report in another template (a new version too, history is kept).
  const fileRef = useRef<HTMLInputElement>(null)
  const [templates, setTemplates] = useState<string[]>([])
  const [tpl, setTpl] = useState('')
  useEffect(() => { api.pget('/api/templates').then(setTemplates).catch(() => {}) }, [])
  const onPickFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f || !sel) return
    try {
      await upload(api.privateBase, `/api/pipeline/reports/${sel.card.id}/version?note=${encodeURIComponent('Uploaded ' + f.name)}`, f)
      toast('New version uploaded.')
      reloadDetail()
    } catch {}
  }
  const regenerate = async () => {
    if (!tpl || !sel) return
    try {
      await api.ppost(`/api/pipeline/reports/${sel.card.id}/template`, { template: tpl })
      toast(`Regenerated as ${tpl}.`)
      reloadDetail()
    } catch {}
  }

  const clients = useMemo(() => [...new Set((cols ?? []).flatMap((c) => c.cards.map((k) => k.client)))], [cols])
  // Derived straight from the live board state (not hardcoded demo lines), so it reflects
  // whatever the team actually has queued up right now: a fresh proposal, a scan in flight,
  // and a rejection with its reason.
  const notif = useMemo(() => {
    if (!cols) return []
    const items: { icon: React.ReactNode; tone: string; text: string }[] = []
    const pending = cols.find((c) => c.id === 'pending')?.cards[0]
    if (pending) items.push({ icon: <FileText size={15} />, tone: 'text-accent', text: `New proposal: ${pending.client}` })
    const scanning = cols.find((c) => c.id === 'scanning')?.cards[0]
    if (scanning) items.push({ icon: <Activity size={15} />, tone: 'text-info', text: `Scanning: ${scanning.client} (${scanning.meta})` })
    const rejected = cols.find((c) => c.id === 'rejected')?.cards[0]
    if (rejected) items.push({ icon: <XIcon size={15} />, tone: 'text-crit', text: `Rejected: ${rejected.client}` })
    return items
  }, [cols])
  const view = useMemo(
    () => (cols ?? []).map((c) => ({ ...c, cards: client ? c.cards.filter((k) => k.client === client) : c.cards })),
    [cols, client],
  )

  // Local optimistic move + a real mutation call. The real API splits what used to be one
  // generic "move" into distinct per-transition endpoints (approve/reject live on the public
  // plane since they act on a proposal; forward/sendback/suspend live on the private plane
  // since they act on a report or job) - the client-side board shape stays the same either way.
  const localMove = (id: string, from: string, to: string, patch?: Partial<Card>) => {
    setCols((cs) => {
      if (!cs) return cs
      const card = cs.find((c) => c.id === from)?.cards.find((k) => k.id === id)
      if (!card) return cs
      const moved = patch ? { ...card, ...patch } : card
      return cs.map((c) => (c.id === from ? { ...c, cards: c.cards.filter((k) => k.id !== id) } : c.id === to ? { ...c, cards: [moved, ...c.cards] } : c))
    })
  }
  // Every mutation below both moves the card optimistically (instant feedback) AND refetches
  // the board once the API call settles - on `.finally`, not just `.then`, so a failed call
  // (a 409 race with another reviewer, a dropped connection) reconciles back to the real state
  // instead of leaving the optimistic move sitting there wrong until the next 8s poll. The
  // trailing .catch(() => {}) just stops that already-toasted (by api.ts) rejection from
  // becoming an unhandled-promise console warning - the refetch already ran regardless.
  const approve = (c: Card, col: string) => {
    localMove(c.id, col, 'scanning')
    api.ppost(`/api/proposals/${c.id}/approve`).then(() => toast(`Approved. Scan queued for ${c.client}.`)).catch(() => {}).finally(refetchBoard)
    setOpen(false)
  }
  const reject = (c: Card, col: string, reason?: string) => {
    const rejectReason = reason?.trim() || 'No reason recorded.'
    localMove(c.id, col, 'rejected', { rejectReason })
    api.ppost(`/api/proposals/${c.id}/reject`, { reason: rejectReason }).then(() => toast(`Proposal rejected: ${c.client}.`)).catch(() => {}).finally(refetchBoard)
    setOpen(false); setRejectNote('')
  }
  const forward = (c: Card, col: string) => {
    const to = STAGES[Math.min(STAGES.indexOf(col) + 1, STAGES.length - 1)]
    localMove(c.id, col, to)
    api.ppost(`/api/pipeline/reports/${c.id}/forward`).then(() => toast(`Forwarded to ${stageName[to]}.`)).catch(() => {}).finally(refetchBoard)
    setOpen(false)
  }
  const back = (c: Card, col: string) => {
    const to = STAGES[Math.max(STAGES.indexOf(col) - 1, 0)]
    localMove(c.id, col, to)
    api.ppost(`/api/pipeline/reports/${c.id}/sendback`).then(() => toast(`Sent back to ${stageName[to]}.`)).catch(() => {}).finally(refetchBoard)
    setOpen(false)
  }
  const toggleSuspend = (c: Card, col: string) => {
    if (!c.jobId) {
      // Can happen for a few hundred ms right after approving, before the post-approve
      // refetch lands - the job didn't exist client-side until the backend created it. Refuse
      // rather than show a false "suspended" toast for a call that never actually fired.
      toast('Still syncing this scan - try again in a moment.')
      return
    }
    const next = !c.suspended
    setCols((cs) => cs?.map((x) => (x.id === col ? { ...x, cards: x.cards.map((k) => (k.id === c.id ? { ...k, suspended: next } : k)) } : x)) ?? cs)
    setSel((s) => (s && s.card.id === c.id ? { ...s, card: { ...s.card, suspended: next } } : s))
    api.ppost(`/api/pipeline/scans/${c.jobId}/${next ? 'suspend' : 'resume'}`).then(() => toast(next ? `Scan suspended for ${c.client}.` : `Scan resumed for ${c.client}.`)).catch(() => {}).finally(refetchBoard)
  }
  const reissuePassword = (c: Card) => {
    // Only claims success once the backend actually confirms it - it used to toast
    // "issued" unconditionally, even on a 403 (only governance may re-issue).
    api.ppost(`/api/pipeline/reports/${c.id}/reissue-password`)
      .then(() => toast(`New view-once password issued for ${c.client}.`))
      .catch(() => {})
    setOpen(false)
  }
  const downloadVersion = (rid: string, v: Version) => {
    download(api.privateBase, `/api/pipeline/reports/${rid}/versions/${v.version_no}/download`, `${rid}_v${v.version_no}.docx`)
  }
  const launchScan = (opts: ScanOpts) => {
    const tools = ['katana', 'nuclei', ...(opts.sqlmap ? ['sqlmap'] : [])]
    api.ppost('/api/scans', { target: opts.target, tools, division: '', opts: toApiOpts(opts) })
      .then(() => toast(`Scan launched: ${opts.target}`))
      .catch(() => {})
  }

  return (
    <div className="mx-auto max-w-[1500px] p-[clamp(10px,2vw,28px)]">
      {/* team header band */}
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
          <span className="rounded-pill bg-[#F4F6F1] px-3.5 py-1.5 text-[13px] font-semibold text-[#12140F]">Board</span>
          <Link to="/team/findings" className="rounded-pill px-3.5 py-1.5 text-[13px] font-medium text-[#F2F5EF]/70">Findings</Link>
        </div>
        <div>
          <div className="flex items-center gap-2 text-[12.5px] text-[#F2F5EF]/70"><Lock size={13} /> Private plane · Tailscale · Security team</div>
          <h1 className="text-[22px] font-bold tracking-[-0.02em]">Review Pipeline</h1>
        </div>
        <div className="ml-auto flex max-w-full flex-wrap items-center gap-2.5">
          <button onClick={() => setScanOpen(true)} className="flex items-center gap-2 whitespace-nowrap rounded-pill bg-[#F4F6F1] px-4 py-2.5 text-[13px] font-semibold text-[#12140F] transition-opacity hover:opacity-90">
            <Plus size={15} /> New scan
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-2 whitespace-nowrap rounded-pill bg-white/[.16] px-4 py-2.5 text-[13px] font-medium text-[#F2F5EF]">
              <Filter size={15} /> {client ?? 'All clients'} <ChevronDown size={14} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setClient(null)}>All clients</DropdownMenuItem>
              <DropdownMenuSeparator />
              {clients.map((cl) => <DropdownMenuItem key={cl} onClick={() => setClient(cl)}>{cl}</DropdownMenuItem>)}
            </DropdownMenuContent>
          </DropdownMenu>
          <ThemeToggle className={ctrl} />
          <DropdownMenu>
            <DropdownMenuTrigger aria-label="Notifications" className={`relative ${ctrl}`}>
              <Bell size={18} />
              {notif.length > 0 && <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-accent ring-2 ring-[#0e211b]" />}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[280px]">
              <DropdownMenuLabel>Notifications</DropdownMenuLabel>
              {notif.length === 0 && <div className="px-3 py-4 text-center text-[12.5px] text-ink-faint">Nothing new.</div>}
              {notif.map((n) => (
                <DropdownMenuItem key={n.text} className="items-start gap-2.5">
                  <span className={`mt-0.5 ${n.tone}`}>{n.icon}</span>
                  <span className="flex-1 text-[13px] text-ink">{n.text}</span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <TeamAccount />
        </div>
      </header>

      {/* kanban */}
      {error ? (
        <ErrorRetry message={error} onRetry={refetchBoard} />
      ) : !cols ? (
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
                          {c.owner && <span className="grid h-6 w-6 place-items-center rounded-full text-[10.5px] font-bold text-white" style={{ background: 'linear-gradient(160deg,#4FB3E8,#0B5FA5)' }}>{c.owner[0]}</span>}
                        </div>
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuLabel>{col.title}</DropdownMenuLabel>
                      {col.id === 'pending' && (
                        <>
                          <DropdownMenuItem onClick={() => approve(c, col.id)} className="text-low focus:bg-low-bg"><Check size={15} /> Approve proposal</DropdownMenuItem>
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
                      {col.id === 'delivered' && <DropdownMenuItem onClick={() => reissuePassword(c)}><KeyRound size={15} /> Re-issue password</DropdownMenuItem>}
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
                  <div><div className="text-ink-muted">Purpose</div><div className="font-semibold text-ink">{detail?.proposal.purpose ?? '—'}</div></div>
                  <div><div className="text-ink-muted">Division</div><div className="font-semibold text-ink">{detail?.proposal.division ?? '—'}</div></div>
                  <div><div className="text-ink-muted">Environment</div><div className="font-semibold text-ink">{detail?.proposal.environment ?? '—'}</div></div>
                  <div><div className="text-ink-muted">Authorization</div>{detail?.proposal.authorized
                    ? <div className="flex items-center gap-1 font-semibold text-low"><Check size={14} /> Attested</div>
                    : <div className="font-semibold text-ink-faint">—</div>}</div>
                </div>
              </section>

              {isReview(sel.col) && (
                <section>
                  <div className="mb-2.5 flex items-center justify-between">
                    <h4 className="text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Versions</h4>
                    <input ref={fileRef} type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" className="hidden" onChange={onPickFile} />
                    <button onClick={() => fileRef.current?.click()} className="flex items-center gap-1.5 text-[12px] font-semibold text-accent hover:opacity-80"><Upload size={13} /> Upload new</button>
                  </div>
                  <div className="mb-3 flex items-center gap-2">
                    <select value={tpl} onChange={(e) => setTpl(e.target.value)} aria-label="Report template" className="min-w-0 flex-1 rounded-input border border-rule bg-panel px-3 py-2 text-[12.5px] text-ink outline-none focus:border-accent">
                      <option value="">Regenerate as template…</option>
                      {templates.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <button onClick={regenerate} disabled={!tpl} className="rounded-pill bg-panel px-3.5 py-2 text-[12px] font-semibold text-ink disabled:opacity-40">Regenerate</button>
                  </div>
                  {!detail?.versions?.length && <div className="rounded-input border border-dashed border-rule px-3.5 py-5 text-center text-[12px] text-ink-faint">No versions yet.</div>}
                  <ul className="space-y-2">
                    {(detail?.versions ?? []).map((v) => (
                      <li key={v.version_no} className="flex items-center gap-3 rounded-input border border-rule bg-panel p-3">
                        <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-card text-[12px] font-bold text-ink">v{v.version_no}</span>
                        <div className="min-w-0 flex-1"><div className="truncate text-[13px] font-medium text-ink">{v.note}</div><div className="text-[11.5px] text-ink-faint">{v.editor} · {whenOf(v.created_at)}</div></div>
                        <button onClick={() => downloadVersion(sel.card.id, v)} aria-label="Download" className="grid h-8 w-8 flex-none place-items-center rounded-full text-ink-muted hover:bg-card hover:text-ink"><Download size={15} /></button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {sel.col === 'scanning' && (
                <section>
                  <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Live progress</h4>
                  {sel.card.jobId ? (
                    <div className="rounded-input border border-rule bg-panel p-4">
                      <ScanProgress jobId={sel.card.jobId} base={api.publicBase} />
                      <p className="mt-3 text-[12px] text-ink-faint">Findings land once the full scan finishes.</p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-3 rounded-input border border-rule bg-panel p-4 text-[13px]">
                      <Activity size={18} className="text-info" /> Still syncing this scan's job id - try reopening in a moment.
                    </div>
                  )}
                </section>
              )}

              {sel.col === 'delivered' && (
                <section>
                  <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Delivery</h4>
                  <div className="flex items-center gap-3 rounded-input border border-rule bg-panel p-3.5 text-[13px]"><FileText size={18} className="text-accent" /> Protected PDF sent · view-once password.</div>
                </section>
              )}

              {sel.col === 'rejected' && (
                <section>
                  <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Reason</h4>
                  <div className="flex items-center gap-3 rounded-input border border-rule bg-panel p-3.5 text-[13px] text-ink">{sel.card.rejectReason ?? 'No reason recorded.'}</div>
                </section>
              )}

              {sel.col === 'pending' && (
                <section>
                  <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Reject reason <span className="normal-case text-ink-faint">(optional, shown to no one but the team)</span></h4>
                  <textarea
                    value={rejectNote}
                    onChange={(e) => setRejectNote(e.target.value)}
                    placeholder="e.g. authorization could not be verified for this target"
                    rows={2}
                    className="w-full resize-none rounded-input border border-rule bg-panel px-3.5 py-3 text-[13px] text-ink placeholder:text-ink-faint outline-none focus:border-accent"
                  />
                </section>
              )}
            </div>

            <div className="sticky bottom-0 flex gap-2.5 border-t border-rule bg-card p-6">
              {sel.col === 'pending' && (
                <>
                  <Button variant="outline" size="lg" className="flex-1" onClick={() => reject(sel.card, sel.col, rejectNote)}><XIcon size={16} /> Reject</Button>
                  <Button size="lg" className="flex-1" onClick={() => approve(sel.card, sel.col)}><Check size={16} /> Approve</Button>
                </>
              )}
              {sel.col === 'rejected' && <DrawerClose asChild><Button size="lg" className="w-full">Close</Button></DrawerClose>}
              {isReview(sel.col) && (
                <>
                  <Button variant="outline" size="lg" className="flex-1" onClick={() => back(sel.card, sel.col)}><ArrowLeft size={16} /> Send back</Button>
                  <Button size="lg" className="flex-1" onClick={() => forward(sel.card, sel.col)}>Forward <ArrowRight size={16} /></Button>
                </>
              )}
              {sel.col === 'delivered' && (
                <Button variant="outline" size="lg" className="w-full" onClick={() => reissuePassword(sel.card)}><KeyRound size={16} /> Re-issue password</Button>
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
      <AdvancedScanDrawer open={scanOpen} onOpenChange={setScanOpen} onLaunch={launchScan} />
    </div>
  )
}
