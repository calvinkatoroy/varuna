import { useEffect, useRef, useState } from 'react'
import { api, download } from '../api'
import { useAuth } from '../auth'
import Button from '../components/Button'

export default function ActiveScans() {
  const { user } = useAuth()
  const [jobId, setJobId] = useState('')
  const [job, setJob] = useState<any>(null)
  const [err, setErr] = useState('')
  const [looking, setLooking] = useState(false)
  const [generating, setGenerating] = useState(false)
  const timer = useRef<any>(null)

  async function load(id: string, showBusy = false) {
    if (!id) return
    if (showBusy) setLooking(true)
    try {
      setJob(await api.get(`/api/scans/${id}`))
      setErr('')
    } catch (e: any) {
      setErr(e.message)
      setJob(null)
    } finally {
      if (showBusy) setLooking(false)
    }
  }

  // Auto-refresh every 5s while queued/running (REQ-24).
  useEffect(() => {
    clearInterval(timer.current)
    if (job && (job.status === 'queued' || job.status === 'running')) {
      timer.current = setInterval(() => load(job.id), 5000)
    }
    return () => clearInterval(timer.current)
  }, [job?.status])

  async function genReport() {
    setGenerating(true)
    try {
      const meta = await api.post(`/api/scans/${job.id}/report`)
      await download(api.publicBase, `/api/reports/${meta.file}/download`, meta.file)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setGenerating(false)
    }
  }

  const isLive = job && (job.status === 'queued' || job.status === 'running')

  return (
    <div className="max-w-2xl space-y-md">
      <h1 className="font-display text-display text-ink">Active Scans</h1>
      <div className="flex gap-xs">
        <input className="input" placeholder="Job ID" value={jobId} onChange={(e) => setJobId(e.target.value)} />
        <Button variant="ghost" busy={looking} busyLabel="Looking up…" onClick={() => load(jobId, true)}>
          Look up
        </Button>
      </div>
      {err && <div className="text-sm text-crit">{err}</div>}
      {job && (
        <div className="card space-y-2xs">
          <div className="flex flex-wrap items-center gap-xs text-sm">
            <span className="text-ink-muted">Status:</span>
            <span className={`font-semibold text-ink ${isLive ? 'status-pulse' : ''}`}>{job.status}</span>
            <span className="text-ink-muted">Agent:</span>
            <span className={job.agent_online ? 'text-low' : 'text-med'}>
              {job.agent_online ? 'online' : 'offline'}
            </span>
          </div>
          {Object.keys(job.per_tool_status || {}).length > 0 && (
            <div className="mono flex flex-wrap gap-sm text-sm text-ink-muted">
              {Object.entries(job.per_tool_status).map(([t, s]) => (
                <span key={t}>
                  {t}: {String(s)}
                </span>
              ))}
            </div>
          )}
          {job.status === 'done' && user!.role === 'standard' && (
            <Button busy={generating} busyLabel="Generating…" onClick={genReport}>
              Generate Executive Summary
            </Button>
          )}
          {job.status === 'done' && user!.role === 'pro' && (
            <div className="text-sm text-info">
              Review findings and generate full reports on the Findings Review page (requires Tailscale).
            </div>
          )}
        </div>
      )}
    </div>
  )
}
