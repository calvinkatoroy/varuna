import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Filter, Lock, FileText, Activity, Plus, ChevronDown, Pause } from 'lucide-react'
import { api, team, type BoardCard, type BoardColumn } from '@/api'
import { ThemeToggle } from '@/components/ThemeToggle'
import { TeamAccount } from '@/components/TeamAccount'
import { BrandMark } from '@/components/BrandMark'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuLabel, DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'
import { AdvancedScanDrawer, toApiOpts, type ScanOpts } from './AdvancedScanDrawer'
import { TaskDrawer, STAGE_LABEL } from './TaskDrawer'
import { SwipeRail, type RailHandle } from '@/components/SwipeRail'
import { ErrorRetry } from '@/components/ErrorRetry'
import { useApiData } from '@/lib/useApiData'
import { revealTiles } from '@/lib/motion'
import { toast } from '@/lib/toast'
import { localTime } from '@/lib/format'

// The server's meta line carries raw UTC times; show the ISO ones in the reader's local time.
const metaText = (c: BoardCard): string =>
  c.stage === 'task' && c.submittedAt ? `Submitted ${localTime(c.submittedAt)}`
    : c.scanState === 'scheduled' && c.startsAt ? `Starts ${localTime(c.startsAt)}`
    : c.stage === 'delivered' && c.deliveredAt ? `${localTime(c.deliveredAt)} · PDF sent`
    : c.meta

const dot: Record<string, string> = {
  accent: 'bg-accent', info: 'bg-info', high: 'bg-high', crit: 'bg-crit', med: 'bg-med', low: 'bg-low',
}
const CARD_LIMIT = 8
const sevChip = (n: number, cls: string, letter: string) =>
  n > 0 ? <span className={`rounded-md px-1.5 py-0.5 text-[12px] font-bold ${cls}`}>{n}{letter}</span> : null

// No backdrop-filter: this header packs 6 controls in one row, and stacking that many blurred
// regions this close together triggers a real Chromium compositor bleed (see ClientTopbar).
const ctrl = 'grid h-11 w-11 place-items-center rounded-full bg-white/[.16] text-[#F2F5EF] transition-colors hover:bg-white/25'

export default function TeamBoard() {
  const { data: cols, error, reload: refetchBoard } = useApiData<BoardColumn[]>(() => team.board())
  const railRef = useRef<RailHandle>(null)
  // Progressive disclosure: a busy stage can hold hundreds of cards. Show the newest few and let
  // the reviewer ask for the rest, instead of an endless scroll (and a heavy page on a phone).
  const [more, setMore] = useState<Record<string, boolean>>({})
  const [stage, setStage] = useState(0)
  const [selId, setSelId] = useState<string | null>(null)
  const [scanOpen, setScanOpen] = useState(false)
  const [client, setClient] = useState<string | null>(null)
  // The open card always comes from the latest board, so its version and actions are never stale.
  const sel = useMemo<BoardCard | null>(() => (selId ? cols?.flatMap((c) => c.cards).find((k) => k.id === selId) ?? null : null), [cols, selId])

  // Reveal only on first load / filter change: keying on `cols` replayed the fade-in (a visible
  // blank flash of the whole board) after every move and on every 8s poll.
  const loaded = !!cols
  useEffect(() => { if (loaded) revealTiles('.pcard') }, [loaded, client])
  // Passive live-update: nothing else pushes scan progress or stage changes to this page. Only
  // polls while something is actually in motion; stops once everything is delivered or closed.
  useEffect(() => {
    const active = cols?.some((c) => !['delivered', 'closed'].includes(c.id) && c.cards.length > 0)
    if (!active) return
    const id = setInterval(refetchBoard, 8000)
    return () => clearInterval(id)
  }, [cols, refetchBoard])

  const clients = useMemo(() => [...new Set((cols ?? []).flatMap((c) => c.cards.map((k) => k.client)))], [cols])
  const notif = useMemo(() => {
    if (!cols) return []
    const items: { icon: React.ReactNode; tone: string; text: string }[] = []
    const fresh = cols.find((c) => c.id === 'task')?.cards[0]
    if (fresh) items.push({ icon: <FileText size={15} />, tone: 'text-accent-ink', text: `New task: ${fresh.client}` })
    const stuck = cols.find((c) => c.id === 'scan')?.cards.find((k) => k.suspended)
    if (stuck) items.push({ icon: <Activity size={15} />, tone: 'text-med', text: `Suspended: ${stuck.client} (${stuck.reason ?? 'no reason'})` })
    const mine = cols.find((c) => c.id.startsWith('review_'))?.cards[0]
    if (mine) items.push({ icon: <FileText size={15} />, tone: 'text-accent-ink', text: `Waiting for your approval: ${mine.client}` })
    return items
  }, [cols])
  const view = useMemo(
    () => (cols ?? []).map((c) => ({ ...c, cards: client ? c.cards.filter((k) => k.client === client) : c.cards })),
    [cols, client],
  )

  // First load: open on the first stage that has work in it (matters most on a phone, where only one stage shows at a time).
  const landed = useRef(false)
  useEffect(() => {
    if (landed.current || !cols) return
    landed.current = true
    const i = cols.findIndex((c) => c.cards.length > 0)
    if (i > 0) setTimeout(() => railRef.current?.scrollToIndex(i), 50)
  }, [cols])

  const launchScan = (opts: ScanOpts) => {
    const tools = ['katana', 'nuclei', ...(opts.sqlmap ? ['sqlmap'] : [])]
    api.ppost('/api/scans', { target: opts.target, tools, division: '', opts: toApiOpts(opts) })
      .then(() => toast(`Scan launched: ${opts.target}`))
      .catch(() => {})
  }

  return (
    <div className="mx-auto max-w-[1500px] p-[clamp(10px,2vw,28px)]">
      <a href="#main" className="sr-only rounded-pill bg-cta-bg px-4 py-2 text-[13px] font-semibold text-cta-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:px-5 focus:py-3 focus:shadow-lg">Skip to content</a>
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
          <span aria-current="page" className="rounded-pill bg-[#F4F6F1] px-4 py-3 text-[13px] font-semibold text-[#12140F] md:px-3.5 md:py-1.5">Board</span>
          <Link to="/team/findings" className="rounded-pill px-4 py-3 text-[13px] font-medium text-[#F2F5EF]/70 md:px-3.5 md:py-1.5">Findings</Link>
        </div>
        <div>
          <div className="flex items-center gap-2 text-[12.5px] text-[#F2F5EF]/70"><Lock size={13} /> Private plane · Tailscale · Security team</div>
          <h1 className="text-[22px] font-bold tracking-[-0.02em]">Task board</h1>
        </div>
        <div className="ml-auto flex max-w-full flex-wrap items-center gap-2.5">
          <button onClick={() => setScanOpen(true)} aria-label="New scan" className="flex h-11 min-w-[44px] items-center justify-center gap-2 whitespace-nowrap rounded-pill bg-[#F4F6F1] px-3 text-[13px] font-semibold text-[#12140F] transition-opacity hover:opacity-90 sm:px-4">
            <Plus size={16} /> <span className="hidden sm:inline">New scan</span>
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger className="flex h-11 items-center gap-2 whitespace-nowrap rounded-pill bg-white/[.16] px-4 text-[13px] font-medium text-[#F2F5EF]">
              <Filter size={15} /> {client ?? 'All clients'} <ChevronDown size={14} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => setClient(null)}>All clients</DropdownMenuItem>
              <DropdownMenuSeparator />
              {clients.map((cl) => <DropdownMenuItem key={cl} onClick={() => setClient(cl)}>{cl}</DropdownMenuItem>)}
            </DropdownMenuContent>
          </DropdownMenu>
          <ThemeToggle className={`${ctrl} hidden md:grid`} />
          <DropdownMenu>
            <DropdownMenuTrigger aria-label="Notifications" className={`relative ${ctrl}`}>
              <Bell size={18} />
              {notif.length > 0 && <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-accent ring-2 ring-[#0e211b]" />}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-[280px]">
              <DropdownMenuLabel>Notifications</DropdownMenuLabel>
              {notif.length === 0 && <div className="px-3 py-4 text-center text-[12.5px] text-ink-muted">Nothing new.</div>}
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

      <main id="main" tabIndex={-1} className="focus:outline-none">
      {/* kanban */}
      {error ? (
        <ErrorRetry message={error} onRetry={refetchBoard} />
      ) : !cols ? (
        <div className="p-10 text-ink-muted">Loading…</div>
      ) : (
        <>
        {/* The stage rail (phones and tablets only: from lg up the column headings already show every stage): the review journey as a strip you can tap or swipe along. The lit chip
            is where you are; its counts show where work is waiting. Replaces a bare 2,000px
            scrollbar that gave no sense of place. */}
        <div role="tablist" aria-label="Board stages" className="no-scrollbar rail -mx-1 mt-3.5 flex gap-1.5 overflow-x-auto px-1 pb-1.5 pt-1 lg:hidden">
          {view.map((col, i) => (
            <button
              key={col.id}
              id={`stage-chip-${i}`}
              role="tab"
              aria-selected={i === stage}
              onClick={() => railRef.current?.scrollToIndex(i)}
              className={`relative flex min-h-[44px] flex-none items-center gap-2 rounded-pill px-4 text-[13px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus ${i === stage ? 'bg-card text-ink' : 'text-ink-muted hover:text-ink'}`}
            >
              <span className={`h-2 w-2 rounded-full ${dot[col.accent]}`} />
              {col.title}
              <span className={`rounded-pill px-2 py-0.5 text-[12px] ${i === stage ? 'bg-panel text-ink' : 'bg-card text-ink-muted'}`}>{col.cards.length}</span>
              <span aria-hidden className={`absolute inset-x-4 bottom-0 h-[3px] rounded-t-full transition-all duration-300 ${dot[col.accent]} ${i === stage ? 'opacity-100' : 'scale-x-0 opacity-0'}`} />
            </button>
          ))}
        </div>
        <SwipeRail ref={railRef} label="Board columns. Swipe sideways to change stage." onActiveChange={(i) => { setStage(i); document.getElementById(`stage-chip-${i}`)?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' }) }} className="gap-3 p-1 lg:mt-5">
          {view.map((col) => (
            <div key={col.id} className="flex w-[86vw] max-w-[340px] flex-none snap-start flex-col md:w-[280px]">
              <div className="mb-2.5 hidden items-center gap-2 px-1 md:flex">
                <span className={`h-2 w-2 rounded-full ${dot[col.accent]}`} />
                <h3 className="text-[13.5px] font-bold text-ink">{col.title}</h3>
                <span className="ml-auto rounded-pill bg-card px-2 py-0.5 text-[12px] font-semibold text-ink-muted">{col.cards.length}</span>
              </div>
              <div className="flex flex-col gap-2.5">
                {col.cards.slice(0, more[col.id] ? col.cards.length : CARD_LIMIT).map((c, idx) => (
                  <button key={c.id} onClick={() => setSelId(c.id)} style={idx < CARD_LIMIT ? { opacity: 0 } : undefined} className="pcard glass-card liquid min-h-[44px] rounded-bento p-3.5 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                    <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
                      <span className="truncate text-[13.5px] font-semibold text-ink">{c.client}</span>
                      <span className="flex flex-none items-center gap-1">
                        {c.scanState && <span className={`flex-none rounded-md px-1.5 py-0.5 text-[12px] font-bold ${c.suspended ? 'bg-med-bg text-med' : 'bg-info/20 text-ink'}`}>{STAGE_LABEL[`scan/${c.scanState}`]}</span>}
                        {c.scanMode === 'cloud' && <span className="flex-none rounded-md bg-info/20 px-1.5 py-0.5 text-[12px] font-bold uppercase text-ink">cloud</span>}
                      </span>
                    </div>
                    <div className="mono mt-0.5 truncate text-[12px] text-ink-muted">{c.target}</div>
                    <div className="mt-2.5 flex items-center gap-1.5">
                      {sevChip(c.sev.c, 'bg-crit-bg text-crit', 'C')}
                      {sevChip(c.sev.h, 'bg-high-bg text-high', 'H')}
                      {sevChip(c.sev.m, 'bg-med-bg text-med', 'M')}
                      {sevChip(c.sev.l, 'bg-low-bg text-low', 'L')}
                      {c.sev.c + c.sev.h + c.sev.m + c.sev.l === 0 && <span className="text-[12px] text-ink-muted">no findings yet</span>}
                    </div>
                    <div className="mt-2.5 flex items-center justify-between gap-2 border-t border-rule pt-2.5">
                      <span className={`flex min-w-0 items-center gap-1.5 text-[12px] ${c.suspended ? 'font-semibold text-med' : 'text-ink-muted'}`}>
                        {c.suspended && <Pause size={12} className="flex-none" />}
                        <span className="truncate">{c.suspended ? 'Suspended' : metaText(c)}</span>
                      </span>
                      {c.assignee && <span title={c.assignee} aria-label={`Assigned to ${c.assignee}`} className="grid h-6 w-6 flex-none place-items-center rounded-full text-[12px] font-bold text-white" style={{ background: 'linear-gradient(160deg,#4FB3E8,#0B5FA5)' }}>{c.assignee[0]}</span>}
                    </div>
                  </button>
                ))}
                {!more[col.id] && col.cards.length > CARD_LIMIT && (
                  <button onClick={() => setMore({ ...more, [col.id]: true })} className="min-h-[44px] rounded-bento border border-dashed border-rule px-3.5 text-[13px] font-semibold text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
                    Show {col.cards.length - CARD_LIMIT} more
                  </button>
                )}
                {col.cards.length === 0 && <div className="rounded-bento border border-dashed border-rule px-3.5 py-6 text-center text-[12px] text-ink-muted">Nothing here yet</div>}
                {!!col.more && <div className="px-1 text-center text-[12px] text-ink-muted">{col.more} older not shown</div>}
              </div>
            </div>
          ))}
        </SwipeRail>
        </>
      )}

      <TaskDrawer card={sel} open={!!selId} onOpenChange={(v) => !v && setSelId(null)} onMoved={refetchBoard} />
      <AdvancedScanDrawer open={scanOpen} onOpenChange={setScanOpen} onLaunch={launchScan} />
      </main>

    </div>
  )
}
