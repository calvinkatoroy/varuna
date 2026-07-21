import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Button from '../components/Button'

const MODES: Record<string, string[]> = {
  'VA Only (Katana + Nuclei)': ['katana', 'nuclei'],
  'Injection Focus (Katana + SQLMap)': ['katana', 'sqlmap'],
  'Full Web (Katana + Nuclei + SQLMap)': ['katana', 'nuclei', 'sqlmap'],
}
const TEMPLATES = ['Executive Summary', 'Full Technical', 'OWASP Web App', 'ILCS Internal']
const WARN = 'Only scan targets you are explicitly authorized to test. Prefer staging over production.'

export default function NewScan() {
  const { user } = useAuth()
  const nav = useNavigate()
  const isPro = user!.role === 'pro'

  const [target, setTarget] = useState('')
  const [division, setDivision] = useState('')
  const [mode, setMode] = useState(Object.keys(MODES)[2])
  const [template, setTemplate] = useState(TEMPLATES[0])
  const [cookie, setCookie] = useState('')
  const [aggressive, setAggressive] = useState(false)
  const [ack, setAck] = useState(false)
  const [msg, setMsg] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setMsg('')
    if (!target) return setErr('Target is required.')
    if (!ack) return setErr('You must confirm authorization.')
    setBusy(true)
    try {
      const body: any = isPro
        ? { target, tools: MODES[mode], opts: { template, cookie, aggressive } }
        : { target, division }
      const res = await api.post('/api/scans', body)
      setMsg(
        res.state === 'pending_approval'
          ? `Submitted. Cloud target awaits Pro approval. Job ${res.job_id}`
          : `Scan dispatched. Job ${res.job_id}`,
      )
    } catch (e: any) {
      if (e.status === 409 && e.message.includes('agent')) {
        setErr(e.message + ' ')
        nav('/install')
      } else setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="max-w-2xl space-y-md">
      <h1 className="font-display text-display text-ink">New Scan</h1>
      <div className="card border-l-2 border-l-info text-sm text-ink-muted">{WARN}</div>

      <div>
        <label className="label">Target {isPro ? '(URL, hostname, or IP)' : '(URL or hostname)'}</label>
        <input className="input" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="http://…" />
      </div>

      {!isPro && (
        <div>
          <label className="label">Division</label>
          <input className="input" value={division} onChange={(e) => setDivision(e.target.value)} />
        </div>
      )}

      {isPro && (
        <>
          <div>
            <label className="label">Scan mode</label>
            <select className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
              {Object.keys(MODES).map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Report template</label>
            <select className="input" value={template} onChange={(e) => setTemplate(e.target.value)}>
              {TEMPLATES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">Session cookie (authenticated scan, optional)</label>
            <input
              type="password"
              className="input"
              value={cookie}
              onChange={(e) => setCookie(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-xs rounded-input border border-crit/40 bg-crit/5 px-xs py-2xs text-sm text-ink">
            <input type="checkbox" checked={aggressive} onChange={(e) => setAggressive(e.target.checked)} />
            <span>
              <span className="font-medium text-high">Enable aggressive SQLMap</span> (--dump / --os-shell).
              Pro only, off by default.
            </span>
          </label>
        </>
      )}

      <label className="flex items-center gap-xs text-sm text-ink-muted">
        <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
        I confirm I am authorized to scan this target.
      </label>

      {err && <div className="text-sm text-crit">{err}</div>}
      {msg && <div className="text-sm text-low">{msg}</div>}
      <Button busy={busy} busyLabel={isPro ? 'Launching…' : 'Submitting…'}>
        {isPro ? 'Launch' : 'Submit'}
      </Button>
    </form>
  )
}
