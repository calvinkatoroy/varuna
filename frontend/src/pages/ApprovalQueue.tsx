import { useEffect, useState } from 'react'
import { api } from '../api'
import Button from '../components/Button'

export default function ApprovalQueue() {
  const [items, setItems] = useState<any[]>([])
  const [reasons, setReasons] = useState<Record<string, string>>({})
  const [busyId, setBusyId] = useState<string | null>(null)
  const [busyAction, setBusyAction] = useState<'approve' | 'reject' | null>(null)
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
    setBusyId(id)
    setBusyAction('approve')
    try {
      await api.post(`/api/approvals/${id}/approve`)
      await load()
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusyId(null)
      setBusyAction(null)
    }
  }
  async function reject(id: string) {
    setBusyId(id)
    setBusyAction('reject')
    try {
      await api.post(`/api/approvals/${id}/reject`, { reason: reasons[id] || 'no reason given' })
      await load()
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusyId(null)
      setBusyAction(null)
    }
  }

  return (
    <div className="max-w-3xl space-y-md">
      <h1 className="font-display text-display text-ink">Approval Queue</h1>
      {err && <div className="text-sm text-crit">{err}</div>}
      {items.length === 0 && <div className="text-ink-faint">No pending requests.</div>}
      {items.map((r) => (
        <div key={r.job_id} className="card space-y-2xs">
          <div className="text-sm">
            <span className="font-semibold text-ink">{r.submitter}</span>{' '}
            <span className="text-ink-muted">({r.division})</span> →{' '}
            <span className="text-ink">{r.target}</span>{' '}
            <span className="text-med">[{r.target_class}]</span>
          </div>
          <div className="mono text-xs text-ink-faint">{r.timestamp}</div>
          <div className="flex gap-xs">
            <input
              className="input flex-1"
              placeholder="Reject reason"
              value={reasons[r.job_id] || ''}
              onChange={(e) => setReasons({ ...reasons, [r.job_id]: e.target.value })}
            />
            <Button
              busy={busyId === r.job_id && busyAction === 'approve'}
              busyLabel="Approving…"
              disabled={busyId === r.job_id && busyAction === 'reject'}
              onClick={() => approve(r.job_id)}
            >
              Approve
            </Button>
            <Button
              variant="danger"
              busy={busyId === r.job_id && busyAction === 'reject'}
              busyLabel="Rejecting…"
              disabled={busyId === r.job_id && busyAction === 'approve'}
              onClick={() => reject(r.job_id)}
            >
              Reject
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}
