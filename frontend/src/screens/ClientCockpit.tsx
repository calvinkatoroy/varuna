import { lazy, Suspense, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowUpRight, Play } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientTopbar } from '@/components/ClientTopbar'
import { AgentStatus } from '@/components/AgentStatus'
import { ErrorRetry } from '@/components/ErrorRetry'
import { PostureBubbles } from '@/components/viz/PostureBubbles'
import { useApiData } from '@/lib/useApiData'
import { useScrollThreshold } from '@/lib/useScrollThreshold'
import { useScrambleText } from '@/lib/useScrambleText'
import { NewProposalDrawer } from './NewProposalDrawer'
import { revealTiles, press } from '@/lib/motion'

const TrendChart = lazy(() => import('@/components/viz/TrendChart'))

const HERO_BG =
  'radial-gradient(130% 120% at 84% -10%, rgba(34,211,197,.30), transparent 45%),' +
  'linear-gradient(158deg,#0B5FA5 0%,#0A2A43 46%,#060F18 100%)'

const statusPill: Record<string, string> = {
  in_review: 'bg-accent-soft text-accent-ink', delivered: 'bg-low-bg text-low',
  scanning: 'bg-[rgba(125,151,216,.16)] text-info', pending: 'bg-med-bg text-med',
}
const statusLabel: Record<string, string> = { in_review: 'In review', delivered: 'Delivered', scanning: 'Scanning', pending: 'Pending' }
const mono = (host: string) => host.replace(/^www\./, '').split('.')[0].slice(0, 2).toUpperCase()

function Drill({ label, to }: { label: string; to?: string }) {
  const nav = useNavigate()
  return (
    <button aria-label={label} onClick={(e) => { press(e.currentTarget); if (to) nav(to, { viewTransition: true }) }}
      className="grid h-9 w-9 flex-none place-items-center rounded-full border border-rule bg-panel text-ink transition-colors hover:border-ink hover:bg-ink hover:text-card">
      <ArrowUpRight size={15} />
    </button>
  )
}
function TileHead({ title, sub, drill = true, to }: { title: string; sub?: string; drill?: boolean; to?: string }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h3 className="text-[18.5px] font-bold tracking-[-0.02em] text-ink">{title}</h3>
        {sub && <div className="mt-1 text-[12.5px] text-ink-muted">{sub}</div>}
      </div>
      {drill && <Drill label={`Open ${title}`} to={to} />}
    </div>
  )
}

function MiniSev({ sev }: { sev: { c: number; h: number; m: number; l: number } }) {
  const total = sev.c + sev.h + sev.m + sev.l
  if (!total) return <span className="text-[11.5px] text-ink-faint">no findings</span>
  const seg: [keyof typeof sev, string][] = [['c', 'crit'], ['h', 'high'], ['m', 'med'], ['l', 'low']]
  return (
    <span className="flex h-1.5 w-[92px] flex-none overflow-hidden rounded-full bg-rule">
      {seg.map(([k, tone]) => sev[k] > 0 && <span key={k} style={{ width: `${(sev[k] / total) * 100}%`, background: `var(--color-${tone})` }} />)}
    </span>
  )
}

// Only work actually underway: a proposal still awaiting approval or a delivered report isn't.
const inProgress = (es: { status: string }[]) => {
  const n = es.filter((e) => e.status === 'scanning' || e.status === 'in_review').length
  return `${n} engagement${n === 1 ? '' : 's'}`
}

export default function ClientCockpit() {
  const nav = useNavigate()
  const shrink = useScrollThreshold<HTMLElement>(65, 'is-shrunk')
  const fade = useScrollThreshold<HTMLDivElement>(55, 'is-faded')
  const { data: d, error, reload } = useApiData<any>(() => api.get('/api/cockpit'))
  const [proposalOpen, setProposalOpen] = useState(false)
  useEffect(() => { if (d) revealTiles('.tile') }, [d])
  const name = useScrambleText(d?.me.name ?? 'there', !!d)
  const p = d?.posture
  // A fresh account has no findings yet, so `trend` can be empty - not just "unlikely", it's the
  // default state on day one, and indexing trend[0] on an empty array used to crash this page.
  const drop = d && d.trend.length ? Math.round(((sum(d.trend[0]) - sum(d.trend[d.trend.length - 1])) / sum(d.trend[0])) * 100) : 0
  function sum(r: any) { return r.critical + r.high + r.medium + r.low }

  // The outer skeleton (hero + main#page-body) always renders, even before data arrives - a page
  // that returns an entirely different tree while loading has no page-body-named element yet,
  // so a page transition landing here has nothing to cross-fade to and flashes instead.
  return (
    <div className="mx-auto max-w-[1380px] p-[clamp(10px,2vw,28px)]">
      {/* HERO: one merged card, position: fixed - out of document flow entirely, so its own
          size changes (shrink on scroll) can never move anything below it. It shrinks its own
          padding on scroll; the content row (greeting/subtitle/actions) fades out fast, well
          before the card finishes shrinking. The nav pill + controls (inside ClientTopbar) don't
          fade - they're what's left once the card is fully compact. `main` below reserves a
          constant gap sized to the hero's COLLAPSED height; at rest the taller expanded hero
          simply overlaps the top of the cards (opaque bg, higher z-index) and recedes on scroll
          to reveal them - the cards themselves never move. */}
      <header
        ref={shrink}
        className="hero-sticky relative isolate flex flex-col overflow-hidden rounded-bento-lg px-[clamp(18px,2.6vw,34px)] text-[#F2F5EF]"
        style={{ borderRadius: '32px 32px 26px 26px', ['--hero-pb' as any]: '38px', ['--hero-pt' as any]: '20px' }}
      >
        {/* Background is its own layer so it can fade to fully transparent as the hero shrinks -
            at rest it reads as one card; once collapsed, only the individually-glassed nav pill
            and controls remain floating, no leftover dark bar behind them. */}
        <div className="hero-bg-fade absolute inset-0 rounded-[inherit]" style={{ background: HERO_BG }} />
        <ClientTopbar />
        <div ref={fade} className="fade-collapse relative z-10 flex flex-wrap items-end justify-between gap-5" style={{ ['--collapse' as any]: '200px' }}>
          <div>
            <h1 className="text-[clamp(30px,4.4vw,52px)] font-bold leading-none tracking-[-0.02em]">Hello, {name}</h1>
            <p className="mt-3.5 text-[14px] text-[#F2F5EF]/72">{d ? `${inProgress(d.engagements)} in progress · ${p.open} open findings` : 'Loading your workspace…'}</p>
          </div>
          <div className="flex items-center gap-[11px]">
            <AgentStatus />
            <Button variant="glass" size="pill" onClick={() => setProposalOpen(true)}>
              <span className="-my-1.5 -ml-2 mr-0.5 grid h-[26px] w-[26px] place-items-center rounded-full bg-[#F2F5EF] text-[#12140F]"><Play size={12} className="fill-current" /></span>
              New Proposal
            </Button>
          </div>
        </div>
      </header>

      {/* Invisible spacer reserving room for the hero at its EXPANDED size - fixed height, never
          toggles a class, never transitions. Since the hero is position: fixed (out of flow),
          nothing here pushes on it; this just stops the (also fixed) hero from overlapping the
          cards while expanded. Because its own height never changes, it can't cause a snap. */}
      <div aria-hidden className="pointer-events-none" style={{ height: 202 }} />

      {/* BENTO */}
      <main className="mt-3.5 grid grid-cols-1 gap-3 lg:grid-cols-3 lg:grid-rows-[auto_1fr]" style={{ viewTransitionName: 'page-body' }}>
        {error ? (
          <ErrorRetry message={error} onRetry={reload} />
        ) : !d ? (
          <div className="col-span-full p-10 text-ink-faint">Loading…</div>
        ) : (
          <>
            {/* Action needed: the one thing a client actually owns here is remediating and
                marking findings fixed - surface that ahead of the read-only posture tiles below,
                rather than making them dig for it. */}
            {p.critical > 0 && (
              <section className="tile col-span-full flex flex-wrap items-center justify-between gap-3 rounded-bento border border-crit-bg bg-crit-bg px-5 py-4" style={{ opacity: 0 }}>
                <div className="flex items-center gap-3.5">
                  <span className="grid h-10 w-10 flex-none place-items-center rounded-full bg-crit text-white"><AlertTriangle size={18} /></span>
                  <div>
                    <b className="text-[14.5px] font-semibold text-ink">{p.critical} critical finding{p.critical > 1 ? 's' : ''} still open</b>
                    <div className="text-[12.5px] text-ink-muted">These need remediation first - review them and mark fixed once resolved.</div>
                  </div>
                </div>
                <Button size="sm" onClick={() => nav('/findings', { viewTransition: true })}>Review findings <ArrowUpRight size={15} /></Button>
              </section>
            )}

            {/* Engagements (merged navigator, tall) */}
            <section className="tile glass-card liquid flex min-w-0 flex-col overflow-hidden rounded-bento p-5 lg:row-span-2" style={{ opacity: 0 }}>
              <TileHead title="Engagements" sub={`${d.engagements.length} active`} to="/proposals" />
              <div className="flex flex-col">
                {d.engagements.map((e: any, i: number) => (
                  <button key={e.id} onClick={() => nav('/findings', { viewTransition: true })}
                    className={`group flex items-center gap-3.5 py-3.5 text-left ${i ? 'border-t border-rule' : ''}`}>
                    <span className="grid h-9 w-9 flex-none place-items-center rounded-[9px] bg-panel font-display text-[12px] font-bold text-ink">{mono(e.target)}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <b className="truncate text-[14.5px] font-semibold text-ink">{e.target}</b>
                        <span className="flex-none rounded-md bg-panel px-1.5 py-0.5 text-[10px] font-bold uppercase text-ink-muted">{e.mode}</span>
                      </div>
                      <div className="mt-2 flex items-center gap-2.5">
                        <MiniSev sev={e.sev} />
                        <span className="whitespace-nowrap text-[11.5px] text-ink-faint">{e.open} open</span>
                        <span className="grid h-[18px] w-[18px] flex-none place-items-center rounded-[5px] text-[10.5px] font-bold" style={{ background: `var(--color-${e.grade === 'A' ? 'low' : e.grade === 'B' ? 'high' : e.grade === 'C' ? 'med' : 'crit'})`, color: 'var(--color-cta-fg)' }}>{e.grade}</span>
                      </div>
                    </div>
                    <span className={`flex-none whitespace-nowrap rounded-pill px-[11px] py-1.5 text-[11.5px] font-semibold ${statusPill[e.status]}`}>{statusLabel[e.status]}</span>
                  </button>
                ))}
              </div>
            </section>

            {/* Posture bubbles */}
            <section className="tile glass-card liquid flex min-w-0 flex-col overflow-hidden rounded-bento p-5" style={{ opacity: 0 }}>
              <TileHead title="Posture Overview" sub="Severity across all engagements" to="/findings" />
              <PostureBubbles posture={p} />
            </section>

            {/* Latest Report - no delivered report yet is a real, reachable state (a brand
                new account, or one still mid-review), not just a mock gap. */}
            <section className="tile glass-card liquid flex min-w-0 flex-col overflow-hidden rounded-bento p-5" style={{ opacity: 0 }}>
              {d.latestReport ? (
                <>
                  <TileHead title="Latest Report" sub={`${d.latestReport.findings} findings · governance signed`} to="/reports" />
                  <div className="mb-5 mt-1 flex flex-col">
                    {[['Engagement', d.latestReport.engagement], ['Delivered', d.latestReport.delivered], ['Templates', `${d.latestReport.templates} available`]].map(([l, v], i) => (
                      <div key={l} className={`flex items-center justify-between gap-3 py-[9px] ${i ? 'border-t border-rule' : ''}`}>
                        <span className="text-[13px] text-ink-muted">{l}</span>
                        <b className="text-[13.5px] font-semibold text-ink">{v}</b>
                      </div>
                    ))}
                  </div>
                  <div className="mt-auto"><Button size="lg" className="w-full" onClick={() => nav('/reports', { viewTransition: true })}>View report <ArrowUpRight size={17} /></Button></div>
                </>
              ) : (
                <>
                  <TileHead title="Latest Report" sub="Nothing delivered yet" to="/reports" drill={false} />
                  <p className="text-[13px] text-ink-muted">Once a scan clears review, your signed report shows up here.</p>
                </>
              )}
            </section>

            {/* Findings Trend (wide) */}
            <section className="tile glass-card liquid flex min-w-0 flex-col overflow-hidden rounded-bento p-5 lg:col-span-2" style={{ opacity: 0 }}>
              <TileHead title="Findings Trend" sub="Open findings by severity · 6 mo" to="/findings" />
              <div className="mb-1 text-[13px] text-ink-muted">{p.open} open now, <span className="font-semibold text-low">down {drop}%</span> over 6 months</div>
              <Suspense fallback={<div className="h-[214px]" />}><TrendChart data={d.trend} /></Suspense>
            </section>
          </>
        )}
      </main>
      <NewProposalDrawer open={proposalOpen} onOpenChange={setProposalOpen} />
    </div>
  )
}
