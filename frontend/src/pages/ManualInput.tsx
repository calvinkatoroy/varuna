import { useState } from 'react'
import { api } from '../api'
import Button from '../components/Button'

export default function ManualInput() {
  const [f, setF] = useState({
    job_id: '',
    name: '',
    severity: 'high',
    host: '',
    url: '',
    description: '',
    evidence: '',
  })
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  function upd(k: string, v: string) {
    setF({ ...f, [k]: v })
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setMsg('')
    if (!f.job_id || !f.name || !f.host) return setErr('Job ID, finding name, and host are required.')
    setBusy(true)
    try {
      await api.ppost(`/api/findings/${f.job_id}/manual`, {
        name: f.name,
        severity: f.severity,
        host: f.host,
        url: f.url,
        description: f.description,
        evidence: f.evidence,
      })
      setMsg('Finding added, correlated, and enriched into the job.')
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="max-w-2xl space-y-md">
      <h1 className="font-display text-display text-ink">Manual Findings Input</h1>
      <p className="text-ink-muted">
        Add findings from manual testing (business logic, access control, auth) into a job.
      </p>
      <div>
        <label className="label">Job ID</label>
        <input className="input" value={f.job_id} onChange={(e) => upd('job_id', e.target.value)} />
      </div>
      <div>
        <label className="label">Finding name</label>
        <input className="input" value={f.name} onChange={(e) => upd('name', e.target.value)} />
      </div>
      <div>
        <label className="label">Severity</label>
        <select className="input" value={f.severity} onChange={(e) => upd('severity', e.target.value)}>
          {['critical', 'high', 'medium', 'low', 'info'].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="label">Host</label>
        <input className="input" value={f.host} onChange={(e) => upd('host', e.target.value)} />
      </div>
      <div>
        <label className="label">URL (optional)</label>
        <input className="input" value={f.url} onChange={(e) => upd('url', e.target.value)} />
      </div>
      <div>
        <label className="label">Description</label>
        <textarea className="input" rows={3} value={f.description} onChange={(e) => upd('description', e.target.value)} />
      </div>
      <div>
        <label className="label">Evidence / reproduction steps (optional)</label>
        <textarea className="input mono" rows={3} value={f.evidence} onChange={(e) => upd('evidence', e.target.value)} />
      </div>
      {err && <div className="text-sm text-crit">{err}</div>}
      {msg && <div className="text-sm text-low">{msg}</div>}
      <Button busy={busy} busyLabel="Adding…">Add finding</Button>
    </form>
  )
}
