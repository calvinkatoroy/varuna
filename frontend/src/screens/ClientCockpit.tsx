import { lazy, Suspense, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, ArrowUpRight, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ShellActions, ShellTitle } from '@/components/ShellSlots'
import { bare, when } from '@/lib/format'
import { AgentStatus } from '@/components/AgentStatus'
import { ErrorRetry } from '@/components/ErrorRetry'
import { PostureBubbles } from '@/components/viz/PostureBubbles'
import { useApiData } from '@/lib/useApiData'
import { FEEDS } from '@/lib/feeds'
import { invalidate } from '@/lib/swr'
import { NewTaskDrawer } from './NewTaskDrawer'
import { CLIENT_LABEL } from '@/lib/workflow'
import { press } from '@/lib/motion'

const TrendChart = lazy(() => import('@/components/viz/TrendChart'))

const statusPill: Record<string, string> = {
  waiting: 'bg-med-bg text-med', accepted: 'bg-accent-soft text-accent-ink', scheduled: 'bg-accent-soft text-accent-ink',
  scanning: 'bg-[rgba(125,151,216,.16)] text-info', paused: 'bg-med-bg text-med',
  in_review: 'bg-accent-soft text-accent-ink', delivered: 'bg-low-bg text-low',
  declined: 'bg-crit-bg text-crit', expired: 'bg-crit-bg text-crit',
}
const statusLabel: Record<string, string> = CLIENT_LABEL
const mono = (host: string) => bare(host).split(/[.:/]/)[0].slice(0, 2).toUpperCase()

function Drill({ label, to }: { label: string; to?: string }) {
  const nav = useNavigate()
  return (
    <button aria-label={label} onClick={(e) => { press(e.currentTarget); if (to) nav(to) }}
      className="grid h-11 w-11 flex-none place-items-center rounded-full border border-rule bg-panel text-ink transition-colors hover:border-ink hover:bg-ink hover:text-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus md:h-9 md:w-9">
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

// Only work actually underway: a task still waiting for a pentester or a delivered report isn't.
const inProgress = (es: { status: string }[]) => {
  const n = es.filter((e) => e.status === 'scanning' || e.status === 'in_review').length
  return `${n} engagement${n === 1 ? '' : 's'}`
}

export default function ClientCockpit() {
  const nav = useNavigate()
  const { data: d, error, reload } = useApiData<any>(FEEDS.cockpit.load, FEEDS.cockpit.key)
  const [taskOpen, setTaskOpen] = useState(false)
  const p = d?.posture
  // A fresh account has no findings yet, so `trend` can be empty - not just "unlikely", it's the
  // default state on day one, and indexing trend[0] on an empty array used to crash this page.
  const drop = d && d.trend.length ? Math.round(((sum(d.trend[0]) - sum(d.trend[d.trend.length - 1])) / sum(d.trend[0])) * 100) : 0
  function sum(r: any) { return r.critical + r.high + r.medium + r.low }

  return (
    <>
      <ShellTitle
        title={`Hello, ${d?.me.name ?? 'there'}`}
        announce="Overview"
        sub={d ? `${inProgress(d.engagements)} in progress · ${p.open} open findings` : 'Loading your workspace…'}
      />
      <ShellActions>
        <AgentStatus />
        <Button variant="glass" size="pill" onClick={() => setTaskOpen(true)}>
          <span className="-my-1.5 -ml-2 mr-0.5 grid h-[26px] w-[26px] place-items-center rounded-full bg-[#F2F5EF] text-[#12140F]"><Play size={12} className="fill-current" /></span>
          New task
        </Button>
      </ShellActions>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3 lg:grid-rows-[auto_1fr]">
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
              <section className="col-span-full flex flex-wrap items-center justify-between gap-3 rounded-bento border border-crit-bg bg-crit-bg px-5 py-4">
                <div className="flex items-center gap-3.5">
                  <span className="grid h-10 w-10 flex-none place-items-center rounded-full bg-crit text-white"><AlertTriangle size={18} /></span>
                  <div>
                    <b className="text-[14.5px] font-semibold text-ink">{p.critical} critical finding{p.critical > 1 ? 's' : ''} still open</b>
                    <div className="text-[12.5px] text-ink-muted">These need remediation first - review them and mark fixed once resolved.</div>
                  </div>
                </div>
                <Button size="sm" className="min-h-[44px] lg:min-h-0" onClick={() => nav('/findings')}>Review findings <ArrowUpRight size={15} /></Button>
              </section>
            )}

            {/* Engagements (merged navigator, tall) */}
            <section className="glass-card liquid flex min-w-0 flex-col overflow-hidden rounded-bento p-5 lg:row-span-2">
              <TileHead title="Engagements" sub={`${d.engagements.length} active`} to="/tasks" />
              <div className="flex flex-col">
                {d.engagements.map((e: any, i: number) => (
                  <button key={e.id} onClick={() => nav('/findings')}
                    className={`group flex items-center gap-3.5 py-3.5 text-left ${i ? 'border-t border-rule' : ''}`}>
                    <span className="grid h-9 w-9 flex-none place-items-center rounded-[9px] bg-panel font-display text-[12px] font-bold text-ink">{mono(e.target)}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <b className="truncate text-[14.5px] font-semibold text-ink" title={e.target}>{bare(e.target)}</b>
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
            <section className="glass-card liquid flex min-w-0 flex-col overflow-hidden rounded-bento p-5">
              <TileHead title="Posture Overview" sub="Severity across all engagements" to="/findings" />
              <PostureBubbles posture={p} />
            </section>

            {/* Latest Report - no delivered report yet is a real, reachable state (a brand
                new account, or one still mid-review), not just a mock gap. */}
            <section className="glass-card liquid flex min-w-0 flex-col overflow-hidden rounded-bento p-5">
              {d.latestReport ? (
                <>
                  <TileHead title="Latest Report" sub={`${d.latestReport.findings} findings · reviewed and delivered`} to="/reports" />
                  <div className="mb-5 mt-1 flex flex-col">
                    {[['Engagement', bare(d.latestReport.engagement)], ['Delivered', when(d.latestReport.delivered)], ['File', d.latestReport.filename || 'Protected PDF']].map(([l, v], i) => (
                      <div key={l} className={`flex items-center justify-between gap-3 py-[9px] ${i ? 'border-t border-rule' : ''}`}>
                        <span className="text-[13px] text-ink-muted">{l}</span>
                        <b className="min-w-0 truncate text-[13.5px] font-semibold text-ink" title={v}>{v}</b>
                      </div>
                    ))}
                  </div>
                  <div className="mt-auto"><Button size="lg" className="w-full" onClick={() => nav('/reports')}>View report <ArrowUpRight size={17} /></Button></div>
                </>
              ) : (
                <>
                  <TileHead title="Latest Report" sub="Nothing delivered yet" to="/reports" drill={false} />
                  <p className="text-[13px] text-ink-muted">Once a scan clears review, your signed report shows up here.</p>
                </>
              )}
            </section>

            {/* Findings Trend (wide) */}
            <section className="glass-card liquid flex min-w-0 flex-col overflow-hidden rounded-bento p-5 lg:col-span-2">
              <TileHead title="Findings Trend" sub="Open findings by severity · 6 mo" to="/findings" />
              <div className="mb-1 text-[13px] text-ink-muted">{p.open} open now, <span className="font-semibold text-low">down {drop}%</span> over 6 months</div>
              <Suspense fallback={<div className="h-[214px]" />}><TrendChart data={d.trend} /></Suspense>
            </section>
          </>
        )}
      </div>
      <NewTaskDrawer open={taskOpen} onOpenChange={setTaskOpen} onCreated={() => { invalidate(FEEDS.tasks.key); reload() }} />
    </>
  )
}
