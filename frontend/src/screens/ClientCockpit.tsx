import { lazy, Suspense, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowUpRight, Play } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientTopbar } from '@/components/ClientTopbar'
import { AgentStatus } from '@/components/AgentStatus'
import { PostureBubbles } from '@/components/viz/PostureBubbles'
import { useLiquidGlassAll } from '@/lib/useLiquidGlass'
import { useHeroShrink } from '@/lib/useHeroShrink'
import { NewProposalDrawer } from './NewProposalDrawer'
import { revealTiles, press } from '@/lib/motion'

const TrendChart = lazy(() => import('@/components/viz/TrendChart'))

const HERO_BG =
  'radial-gradient(130% 120% at 84% -10%, rgba(242,106,67,.32), transparent 45%),' +
  'linear-gradient(158deg,#154739 0%,#0d211b 46%,#070908 100%)'

const gradeTone: Record<string, string> = { A: 'bg-low', B: 'bg-high', C: 'bg-med', D: 'bg-crit' }
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

export default function ClientCockpit() {
  const nav = useNavigate()
  const hero = useHeroShrink<HTMLElement>(70)
  const [d, setD] = useState<any>(null)
  const [proposalOpen, setProposalOpen] = useState(false)
  useEffect(() => { api.get('/api/cockpit').then(setD) }, [])
  useEffect(() => { if (d) revealTiles('.tile') }, [d])
  useLiquidGlassAll('.glass-card', { scale: -62, blur: 2, mapBlur: 10, saturate: 1.25, chroma: 0 }, [d])

  if (!d) return <div className="p-10 text-ink-faint">Loading…</div>
  const p = d.posture
  const first = d.trend[0], last = d.trend[d.trend.length - 1]
  const sum = (r: any) => r.critical + r.high + r.medium + r.low
  const drop = Math.round(((sum(first) - sum(last)) / sum(first)) * 100)

  return (
    <div ref={hero} className="mx-auto max-w-[1380px] p-[clamp(10px,2vw,28px)]">
      {/* HERO: sticky + shrinks on scroll (title/subtitle fade, topbar stays put) */}
      <header
        className="hero-sticky relative isolate flex flex-col overflow-hidden rounded-bento-lg px-[clamp(18px,2.6vw,34px)] text-[#F2F5EF]"
        style={{ background: HERO_BG, borderRadius: '32px 32px 26px 26px', ['--hero-pb' as any]: '38px', ['--hero-pt' as any]: '20px' }}
      >
        <ClientTopbar />
        <div className="hero-fade relative z-10 mt-3.5 flex flex-wrap items-end justify-between gap-5">
          <div>
            <h1 className="text-[clamp(30px,4.4vw,52px)] font-bold leading-none tracking-[-0.02em]">Hello, {d.me.name}</h1>
            <p className="mt-3.5 text-[14px] text-[#F2F5EF]/72">{d.engagements.length} engagements in progress · {p.open} open findings</p>
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

      {/* BENTO */}
      <main className="content-offset grid grid-cols-1 gap-3 lg:grid-cols-3 lg:grid-rows-[auto_1fr]" style={{ viewTransitionName: 'page-body' }}>
        {/* Engagements (merged navigator, tall) */}
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5 lg:row-span-2" style={{ opacity: 0 }}>
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
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5" style={{ opacity: 0 }}>
          <TileHead title="Posture Overview" sub="Severity across all engagements" to="/findings" />
          <PostureBubbles posture={p} />
        </section>

        {/* Latest Report */}
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5" style={{ opacity: 0 }}>
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
        </section>

        {/* Findings Trend (wide) */}
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5 lg:col-span-2" style={{ opacity: 0 }}>
          <TileHead title="Findings Trend" sub="Open findings by severity · 6 mo" to="/findings" />
          <div className="mb-1 text-[13px] text-ink-muted">{p.open} open now, <span className="font-semibold text-low">down {drop}%</span> over 6 months</div>
          <Suspense fallback={<div className="h-[214px]" />}><TrendChart data={d.trend} /></Suspense>
        </section>
      </main>
      <NewProposalDrawer open={proposalOpen} onOpenChange={setProposalOpen} />
    </div>
  )
}
