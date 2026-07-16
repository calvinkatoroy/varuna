import { useEffect, useState } from 'react'
import { api } from '../api'

export default function ApprovalQueue() {
  const [items, setItems] = useState<any[]>([])
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [err, setErr] = useState('')

  async function load() {
    try {
      setItems(await api.get('/api/approvals'))
    } catch (e: any) {
      setErr(e.message)
    }
  }
  useEffect(() => {
    load()
  }, [])

  async function approve(id: string) {
    try {
      await api.post(`/api/approvals/${id}/approve`)
      load()
    } catch (e: any) {
      setErr(e.message)
    }
  }
  async function reject(id: string) {
    try {
      await api.post(`/api/approvals/${id}/reject`, { reason: reasons[id] || 'no reason given' })
      load()
    } catch (e: any) {
      setErr(e.message)
    }
  }

  return (
    <div className="max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold text-white">Approval Queue</h1>
      {err && <div className="text-sm text-crit">{err}</div>}
      {items.length === 0 && <div className="text-gray-400">No pending requests.</div>}
      {items.map((r) => (
        <div key={r.job_id} className="card space-y-2">
          <div className="text-sm">
            <span className="font-semibold text-white">{r.submitter}</span>{' '}
            <span className="text-gray-400">({r.division})</span> →{' '}
            <span className="text-gray-200">{r.target}</span>{' '}
            <span className="text-med">[{r.target_class}]</span>
          </div>
          <div className="text-xs text-gray-500">{r.timestamp}</div>
          <div className="flex gap-2">
            <input
              className="input flex-1"
              placeholder="Reject reason"
              value={reasons[r.job_id] || ''}
              onChange={(e) => setReasons({ ...reasons, [r.job_id]: e.target.value })}
            />
            <button className="btn" onClick={() => approve(r.job_id)}>
              Approve
            </button>
            <button className="btn-ghost" onClick={() => reject(r.job_id)}>
              Reject
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
