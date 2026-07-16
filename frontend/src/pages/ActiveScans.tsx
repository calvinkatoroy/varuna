import { useEffect, useRef, useState } from 'react'
import { api, download } from '../api'
import { useAuth } from '../auth'

export default function ActiveScans() {
  const { user } = useAuth()
  const [jobId, setJobId] = useState('')
  const [job, setJob] = useState<any>(null)
  const [err, setErr] = useState('')
  const timer = useRef<any>(null)

  async function load(id: string) {
    if (!id) return
    try {
      setJob(await api.get(`/api/scans/${id}`))
      setErr('')
    } catch (e: any) {
      setErr(e.message)
      setJob(null)
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
    try {
      const meta = await api.post(`/api/scans/${job.id}/report`)
      await download(api.publicBase, `/api/reports/${meta.file}/download`, meta.file)
    } catch (e: any) {
      setErr(e.message)
    }
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold text-white">Active Scans</h1>
      <div className="flex gap-2">
        <input className="input" placeholder="Job ID" value={jobId} onChange={(e) => setJobId(e.target.value)} />
        <button className="btn" onClick={() => load(jobId)}>
          Look up
        </button>
      </div>
      {err && <div className="text-sm text-crit">{err}</div>}
      {job && (
        <div className="card space-y-2">
          <div>
            <span className="text-gray-400">Status:</span>{' '}
            <span className="font-semibold text-white">{job.status}</span>
            <span className="ml-4 text-gray-400">Agent:</span>{' '}
            <span className={job.agent_online ? 'text-low' : 'text-med'}>
              {job.agent_online ? 'online' : 'offline'}
            </span>
          </div>
          {Object.keys(job.per_tool_status || {}).length > 0 && (
            <div className="text-sm text-gray-300">
              {Object.entries(job.per_tool_status).map(([t, s]) => (
                <span key={t} className="mr-3">
                  {t}: {String(s)}
                </span>
              ))}
            </div>
          )}
          {job.status === 'done' && user!.role === 'standard' && (
            <button className="btn" onClick={genReport}>
              Generate Executive Summary
            </button>
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
