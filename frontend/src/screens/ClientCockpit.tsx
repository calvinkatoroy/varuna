import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ArrowUpRight, Bell, Check, ChevronsUp, CircleAlert, Clock, Download, FileText,
  Lock, Play, Plus, Shield, ShieldCheck, TriangleAlert, CalendarDays, LayoutTemplate,
} from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ThemeToggle } from '@/components/ThemeToggle'
import { ClientNav } from '@/components/ClientNav'
import { useLiquidGlassAll } from '@/lib/useLiquidGlass'
import { NewProposalDrawer } from './NewProposalDrawer'
import { revealTiles, tickNumber, press } from '@/lib/motion'

const TrendChart = lazy(() => import('@/components/viz/TrendChart'))

const HERO_BG =
  'radial-gradient(130% 120% at 84% -10%, rgba(242,106,67,.32), transparent 45%),' +
  'linear-gradient(158deg,#154739 0%,#0d211b 46%,#070908 100%)'

function Drill({ label, to }: { label: string; to?: string }) {
  const nav = useNavigate()
  return (
    <button
      aria-label={label}
      onClick={(e) => { press(e.currentTarget); if (to) nav(to) }}
      className="grid h-9 w-9 flex-none place-items-center rounded-full border border-rule bg-panel text-ink transition-colors hover:border-ink hover:bg-ink hover:text-card"
    >
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

function Stat({ tone, icon, n, unit, label }: any) {
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => tickNumber(ref.current, n), [n])
  const ring: Record<string, string> = {
    c: 'border-crit text-crit', h: 'border-high text-high', m: 'border-med text-med',
    l: 'border-low text-low', o: 'border-ink-faint text-ink-muted', s: 'border-accent text-accent',
  }
  return (
    <div className="flex items-center gap-3.5">
      <span className={`grid h-[46px] w-[46px] flex-none place-items-center rounded-full border-[1.5px] ${ring[tone]}`}>{icon}</span>
      <div>
        <div className="text-[23px] font-bold leading-none tracking-[-0.02em] text-ink">
          <span ref={ref}>0</span>
          {unit && <small className="ml-0.5 text-[13px] font-semibold text-ink-faint">{unit}</small>}
        </div>
        <div className="mt-[5px] text-[12px] text-ink-muted">{label}</div>
      </div>
    </div>
  )
}

const gradeTone: Record<string, string> = { A: 'bg-low', B: 'bg-high', C: 'bg-med', D: 'bg-crit' }
const stageBadge: Record<string, string> = {
  in_review: 'bg-accent-soft text-accent-ink', delivered: 'bg-low-bg text-low', scanning: 'bg-[rgba(125,151,216,.16)] text-info',
}
const stageLabel: Record<string, string> = { in_review: 'In review', delivered: 'Delivered', scanning: 'Scanning' }
const teamBadge = (s: string) => (s === 'In review' ? 'bg-accent-soft text-accent-ink' : 'bg-low-bg text-low')
const avaBg = ['linear-gradient(160deg,#3fb98a,#268a63)', 'linear-gradient(160deg,#f4996d,#F26A43)', 'linear-gradient(160deg,#7b86ee,#4a56c9)']

// The scanned site's own favicon, with a letter monogram fallback. Mock/demo uses a public
// favicon service; PRODUCTION: the agent grabs /favicon.ico from the target during the scan and
// stores it locally (on-premise), never a third-party lookup that would leak client hostnames.
function AssetIcon({ host }: { host: string }) {
  const [err, setErr] = useState(false)
  const clean = host.replace(/^www\./, '')
  return (
    <span className="mx-auto mb-2.5 grid h-[38px] w-[38px] place-items-center overflow-hidden rounded-[11px] bg-panel text-[15px] font-semibold text-ink">
      {err
        ? (clean[0]?.toUpperCase() ?? '?')
        : <img src={`https://icons.duckduckgo.com/ip3/${clean}.ico`} alt="" width={20} height={20} loading="lazy" onError={() => setErr(true)} className="h-5 w-5 rounded-[4px]" />}
    </span>
  )
}

export default function ClientCockpit() {
  const [d, setD] = useState<any>(null)
  const [proposalOpen, setProposalOpen] = useState(false)
  useEffect(() => {
    api.get('/api/cockpit').then(setD)
  }, [])
  useEffect(() => {
    if (d) revealTiles('.tile')
  }, [d])
  // Liquid glass on every bento tile, floating over the page gradient.
  useLiquidGlassAll('.glass-card', { scale: -62, blur: 2, mapBlur: 10, saturate: 1.25, chroma: 0 }, [d])

  if (!d) return <div className="p-10 text-ink-faint">Loading…</div>
  const p = d.posture

  return (
    <div className="mx-auto max-w-[1380px] p-[clamp(10px,2vw,28px)]">
      {/* HERO */}
      <header
        className="relative isolate flex min-h-[340px] flex-col overflow-hidden rounded-bento-lg px-[clamp(18px,2.6vw,34px)] pb-[clamp(24px,3vw,38px)] pt-[clamp(16px,2vw,24px)] text-[#F2F5EF]"
        style={{ background: HERO_BG, borderRadius: '32px 32px 26px 26px' }}
      >
        <div className="relative z-10 flex items-center gap-4">
          <div className="flex items-center gap-[11px] text-[21px] font-bold tracking-[-0.02em]">
            <span className="grid h-8 w-8 place-items-center rounded-[10px]" style={{ background: 'conic-gradient(from 210deg,#F26A43,#f4996d,#F26A43)', boxShadow: 'inset 0 0 0 2px rgba(255,255,255,.16)' }}>
              <Shield size={18} className="fill-white text-white" />
            </span>
            Varuna
          </div>
          <ClientNav />
          <div className="flex gap-2.5">
            <ThemeToggle />
            <button aria-label="Notifications" className="grid h-11 w-11 place-items-center rounded-full bg-white/10 backdrop-blur-md transition-colors hover:bg-white/[.18]"><Bell size={19} /></button>
            <button aria-label="Account" className="grid h-11 w-11 place-items-center overflow-hidden rounded-full text-sm font-bold text-white" style={{ background: 'linear-gradient(160deg,#f4996d,#F26A43)' }}>AC</button>
          </div>
        </div>

        <div className="relative z-10 mt-auto flex flex-wrap items-end justify-between gap-5">
          <div>
            <div className="flex items-center gap-[9px] text-[13.5px] text-[#F2F5EF]/72">
              <span className="inline-flex items-center gap-1.5"><span className="h-[7px] w-[7px] rounded-full bg-low shadow-[0_0_0_3px_rgba(66,196,162,.28)]" /> Live</span>
              · Target · Public web · api.acme.io
            </div>
            <h1 className="mt-3 text-[clamp(30px,4.6vw,56px)] font-bold leading-none tracking-[-0.02em]" style={{ textWrap: 'balance' as any }}>
              Acme Web App<span className="block font-medium text-[#cfe0d3]">Security Assessment</span>
            </h1>
          </div>
          <div className="flex gap-[11px]">
            <Button variant="glass" size="pill"><Plus size={16} /> Install Agent</Button>
            <Button variant="glass" size="pill" onClick={() => setProposalOpen(true)}>
              <span className="-my-1.5 -ml-2 mr-0.5 grid h-[26px] w-[26px] place-items-center rounded-full bg-[#F2F5EF] text-[#12140F]"><Play size={12} className="fill-current" /></span>
              New Proposal
            </Button>
          </div>
        </div>
      </header>

      {/* BENTO */}
      <main className="mt-3.5 grid grid-cols-1 gap-3 lg:grid-cols-[1fr_1.16fr_1fr]">
        {/* 1 · Engagements */}
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5" style={{ opacity: 0 }}>
          <TileHead title="Engagements" sub="June 20 · 3 active" drill={false} />
          <ul className="flex flex-col">
            {d.engagements.map((e: any, i: number) => (
              <li key={e.id} className={`flex items-center gap-3.5 py-[11px] ${i ? 'border-t border-rule' : ''}`}>
                <span className={`min-w-[66px] flex-none rounded-pill border-[1.5px] px-3 py-[9px] text-center text-[12.5px] font-semibold ${e.when === '2h ago' ? 'border-primary bg-primary text-primary-foreground' : 'border-rule text-ink-muted'}`}>{e.when}</span>
                <div className="min-w-0 flex-1"><b className="block truncate text-[14.5px] font-semibold text-ink">{e.target}</b><span className="text-[12.5px] text-ink-muted">{e.detail}</span></div>
                <span className={`flex-none whitespace-nowrap rounded-pill px-[11px] py-1.5 text-[11.5px] font-semibold ${stageBadge[e.status]}`}>{stageLabel[e.status]}</span>
              </li>
            ))}
          </ul>
        </section>

        {/* 2 · Posture */}
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5" style={{ opacity: 0 }}>
          <TileHead title="Posture Overview" sub="Engagement ID: AC-WEB-0712" to="/findings" />
          <div className="mt-0.5 grid grid-cols-2 gap-x-6 gap-y-4">
            <Stat tone="c" n={p.critical} label="Critical findings" icon={<TriangleAlert size={20} />} />
            <Stat tone="h" n={p.high} label="High findings" icon={<ChevronsUp size={20} />} />
            <Stat tone="m" n={p.medium} label="Medium findings" icon={<CircleAlert size={20} />} />
            <Stat tone="l" n={p.low} label="Low findings" icon={<Check size={20} />} />
            <Stat tone="o" n={p.open} unit={`/ ${p.total}`} label={`Open · ${p.fixed} fixed`} icon={<Clock size={20} />} />
            <Stat tone="s" n={p.hygiene} unit="/100" label="Hygiene score" icon={<ShieldCheck size={20} />} />
          </div>
        </section>

        {/* 3 · Findings Trend (Tremor) */}
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5" style={{ opacity: 0 }}>
          <TileHead title="Findings Trend" sub="Open findings · last 6 mo" to="/findings" />
          <Suspense fallback={<div className="h-[168px]" />}>
            <TrendChart data={d.trend} />
          </Suspense>
        </section>

        {/* 4 · Assets */}
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5" style={{ opacity: 0 }}>
          <TileHead title="Your Assets" sub="4 in scope" to="/findings" />
          <div className="grid grid-cols-2 gap-[11px]">
            {d.assets.map((a: any) => (
              <div key={a.host} className="rounded-[16px] border border-rule p-[15px] text-center">
                <AssetIcon host={a.host} />
                <b className="block truncate text-[13.5px] font-semibold text-ink">{a.host}</b>
                <div className="mt-[11px] flex items-center justify-between">
                  <span className="inline-flex items-center gap-[5px] text-[11.5px] font-bold text-ink">
                    <span className={`grid h-5 w-5 place-items-center rounded-[6px] text-[11px] text-cta-fg ${gradeTone[a.grade]}`} style={{ color: 'var(--color-cta-fg)' }}>{a.grade}</span>{a.label}
                  </span>
                  <span className="text-[11px] text-ink-faint">{a.open} open</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 5 · Latest Report */}
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5" style={{ opacity: 0 }}>
          <TileHead title="Latest Report" sub={`${d.latestReport.findings} findings · governance signed`} to="/reports" />
          <div className="my-1.5 mb-5 flex flex-col gap-3.5">
            {[
              { ic: <FileText size={15} />, l: 'Engagement', v: d.latestReport.engagement },
              { ic: <CalendarDays size={15} />, l: 'Delivered', v: d.latestReport.delivered },
              { ic: <LayoutTemplate size={15} />, l: 'Templates', v: `${d.latestReport.templates} available` },
            ].map((r) => (
              <div key={r.l} className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-[11px] text-[13px] text-ink-muted"><span className="grid h-8 w-8 flex-none place-items-center rounded-[9px] border border-rule text-accent">{r.ic}</span>{r.l}</span>
                <b className="text-[13.5px] font-semibold text-ink">{r.v}</b>
              </div>
            ))}
          </div>
          <div className="mt-auto">
            <Button size="lg" className="w-full"><Download size={17} /> Download protected PDF</Button>
            <button className="mt-[11px] flex w-full items-center justify-center gap-[7px] text-[12.5px] font-semibold text-ink-muted"><Lock size={14} /> Reveal password (view-once)</button>
          </div>
        </section>

        {/* 6 · Review Team */}
        <section className="tile glass-card liquid flex min-w-0 flex-col rounded-bento p-5" style={{ opacity: 0 }}>
          <TileHead title="Review Team" sub="3 members on this engagement" />
          <ul className="flex flex-col">
            {d.team.map((m: any, i: number) => (
              <li key={m.name} className={`flex items-center gap-3.5 py-[11px] ${i ? 'border-t border-rule' : ''}`}>
                <span className="grid h-11 w-11 flex-none place-items-center rounded-full text-base font-bold text-white" style={{ background: avaBg[i] }}>{m.name[0]}</span>
                <div className="min-w-0 flex-1"><b className="block text-[14.5px] font-semibold text-ink">{m.name}</b><span className="text-[12.5px] text-ink-muted">{m.role}</span></div>
                <span className={`flex-none whitespace-nowrap rounded-pill px-[11px] py-1.5 text-[11.5px] font-semibold ${teamBadge(m.status)}`}>{m.status}</span>
              </li>
            ))}
          </ul>
        </section>
      </main>
      <NewProposalDrawer open={proposalOpen} onOpenChange={setProposalOpen} />
    </div>
  )
}
