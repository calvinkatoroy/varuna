import { useEffect, useState } from 'react'
import { api } from '../api'
import Button from '../components/Button'

export default function InstallAgent() {
  const [status, setStatus] = useState<{ registered: boolean; online: boolean } | null>(null)
  const [token, setToken] = useState('')
  const [err, setErr] = useState('')
  const [generating, setGenerating] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

  async function refresh(showBusy = false) {
    if (showBusy) setRefreshing(true)
    try {
      setStatus(await api.get('/api/agent'))
    } catch (e: any) {
      setErr(e.message)
    } finally {
      if (showBusy) setRefreshing(false)
    }
  }
  useEffect(() => {
    refresh()
  }, [])

  async function generate() {
    setErr('')
    setGenerating(true)
    try {
      const { enrollment_token } = await api.post('/api/agent/install-token')
      setToken(enrollment_token)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="max-w-2xl space-y-md">
      <h1 className="font-display text-display text-ink">Install Your Agent</h1>
      <p className="text-ink-muted">
        The agent runs scans on your own machine and reports back. Install it once, then submit
        scans as normal.
      </p>
      {status && (
        <div className="card text-sm">
          Status:{' '}
          <span className={status.registered ? 'text-low' : 'text-med'}>
            {status.registered ? (status.online ? 'registered · online' : 'registered · offline') : 'not registered'}
          </span>
        </div>
      )}
      <Button busy={generating} busyLabel="Generating…" onClick={generate}>
        Generate enrollment token
      </Button>
      {token && (
        <div className="card space-y-xs">
          <div className="text-sm text-ink-muted">On your Windows machine, open PowerShell and paste:</div>
          <pre className="mono overflow-x-auto rounded-input bg-paper p-xs text-sm text-low">{`$env:VARUNA_URL='${window.location.origin}'; $env:VARUNA_TOKEN='${token}'; irm ${window.location.origin}/dist/install.ps1 | iex`}</pre>
          <Button variant="ghost" busy={refreshing} busyLabel="Refreshing…" onClick={() => refresh(true)}>
            I’ve installed it, refresh
          </Button>
        </div>
      )}
      {err && <div className="text-sm text-crit">{err}</div>}
    </div>
  )
}
