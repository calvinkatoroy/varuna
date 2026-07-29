import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

// Status colors are independent of --color-accent on purpose: accent doubles as the
// primary-button fill (near-black in the warm theme), so tying a status color to it
// made "running" collide visually with body ink. Each status gets its own hue instead.
const STATUS_CLS: Record<string, string> = {
  queued: 'text-info',
  running: 'text-med status-pulse',
  done: 'text-low',
  failed: 'text-crit',
  pending_approval: 'text-ink-faint',
}

const STATUS_BAR_BG: Record<string, string> = {
  queued: 'bg-info',
  running: 'bg-med',
  done: 'bg-low',
  failed: 'bg-crit',
  pending_approval: 'bg-ink-faint',
}

export default function Dashboard() {
  const { user } = useAuth()
  const isPro = user!.role === 'pro'
  const navigate = useNavigate()

  const [agent, setAgent] = useState<{ registered: boolean; online: boolean } | null>(null)
  const [jobs, setJobs] = useState<any[] | null>(null)
  const [approvals, setApprovals] = useState<any[] | null>(null)
  const [reports, setReports] = useState<any[] | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.get('/api/agent').then(setAgent).catch((e) => setErr(e.message))
    api.get('/api/scans').then(setJobs).catch((e) => setErr(e.message))
    api.get('/api/reports').then(setReports).catch((e) => setErr(e.message))
    if (isPro) api.get('/api/approvals').then(setApprovals).catch((e) => setErr(e.message))
  }, [isPro])

  // Real counts only, never a stat the API didn't actually return.
  const statusCounts: Record<string, number> = {}
  jobs?.forEach((j) => {
    statusCounts[j.status] = (statusCounts[j.status] || 0) + 1
  })
  const total = jobs?.length || 0

  return (
    <div className="dashboard-warm -m-sm p-sm md:-m-lg md:p-lg">
      <div className="mx-auto max-w-6xl space-y-sm md:space-y-md">
        <div className="banner flex flex-wrap items-center justify-between gap-sm px-sm py-md md:px-lg">
          <div className="flex flex-wrap items-center gap-sm">
            <span className="font-display text-2xl">Dashboard</span>
            {agent && (
              <span
                className={`text-sm ${agent.registered ? (agent.online ? 'text-low' : 'text-med') : 'text-crit'}`}
              >
                agent: {agent.registered ? (agent.online ? 'online' : 'offline') : 'not installed'}
              </span>
            )}
          </div>
          <Link to="/new" className="btn whitespace-nowrap !rounded-pill">
            New scan
          </Link>
        </div>

        {err && <div className="glass px-sm py-2xs text-sm text-crit md:px-md">{err}</div>}

        {agent && !agent.registered && (
          <div className="glass flex flex-wrap items-center justify-between gap-sm border-l-2 !border-l-med px-sm py-xs md:px-md">
            <div className="text-sm text-ink">
              No agent installed. You can't launch scans until one is registered.
            </div>
            <Link to="/install" className="btn-ghost whitespace-nowrap">
              Install agent
            </Link>
          </div>
        )}

        {total > 0 && (
          <div className="glass space-y-2xs px-sm py-xs md:px-md">
            <div className="text-xs font-medium uppercase tracking-wide text-ink-faint">
              Scan activity ({total} recent)
            </div>
            <div className="status-bar">
              {Object.entries(statusCounts).map(([status, count]) => (
                <div
                  key={status}
                  className={STATUS_BAR_BG[status] || 'bg-ink-faint'}
                  style={{ width: `${(count / total) * 100}%` }}
                  title={`${status}: ${count}`}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-sm text-xs text-ink-muted">
              {Object.entries(statusCounts).map(([status, count]) => (
                <span key={status} className="flex items-center gap-2xs">
                  <span className={`h-2 w-2 rounded-pill ${STATUS_BAR_BG[status] || 'bg-ink-faint'}`} />
                  {status} · {count}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="grid gap-sm md:grid-cols-[minmax(0,1fr)_320px] md:gap-md">
          <div className="glass overflow-hidden">
            <div className="border-b border-rule px-sm py-2xs text-xs font-medium uppercase tracking-wide text-ink-faint md:px-md">
              Recent jobs
            </div>
            {jobs && jobs.length === 0 && (
              <div className="px-sm py-sm text-sm text-ink-faint md:px-md">No scans yet.</div>
            )}
            {jobs && jobs.length > 0 && (
              <div className="overflow-x-auto">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th className="pl-sm md:pl-md">Job</th>
                      <th>Target</th>
                      <th>Status</th>
                      <th className="pr-sm md:pr-md">Tools</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((j) => (
                      <tr
                        key={j.id}
                        tabIndex={0}
                        onClick={() => navigate(`/scans?job=${j.id}`)}
                        onKeyDown={(e) => e.key === 'Enter' && navigate(`/scans?job=${j.id}`)}
                        className="cursor-pointer hover:bg-paper-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-inset"
                      >
                        <td className="mono pl-sm text-xs text-ink-faint md:pl-md">{j.id.slice(0, 8)}</td>
                        <td className="max-w-[16rem] truncate text-ink">{j.target}</td>
                        <td className={STATUS_CLS[j.status] || 'text-ink-muted'}>{j.status}</td>
                        <td className="mono pr-sm text-xs text-ink-muted md:pr-md">{(j.tools || []).join(' ')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="space-y-sm">
            {isPro && (
              <div className="glass px-sm py-xs md:px-md">
                <div className="mb-2xs flex items-center justify-between">
                  <span className="text-xs font-medium uppercase tracking-wide text-ink-faint">Approvals</span>
                  <Link to="/approvals" className="whitespace-nowrap text-xs text-accent hover:underline">
                    {approvals ? approvals.length : '…'} →
                  </Link>
                </div>
                {approvals && approvals.length === 0 && (
                  <div className="text-xs text-ink-faint">Nothing pending.</div>
                )}
                {approvals &&
                  approvals.slice(0, 5).map((r) => (
                    <div key={r.job_id} className="truncate py-3xs text-xs text-ink-muted">
                      <span className="text-ink">{r.submitter}</span> → {r.target}
                    </div>
                  ))}
              </div>
            )}
            <div className="glass px-sm py-xs md:px-md">
              <div className="mb-2xs flex items-center justify-between">
                <span className="text-xs font-medium uppercase tracking-wide text-ink-faint">Reports</span>
                <Link to="/reports" className="whitespace-nowrap text-xs text-accent hover:underline">
                  {reports ? reports.length : '…'} →
                </Link>
              </div>
              {reports && reports.length === 0 && <div className="text-xs text-ink-faint">None yet.</div>}
              {reports &&
                reports.slice(0, 5).map((r) => (
                  <div key={r.file} className="truncate py-3xs text-xs text-ink-muted">
                    {r.file}
                  </div>
                ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
