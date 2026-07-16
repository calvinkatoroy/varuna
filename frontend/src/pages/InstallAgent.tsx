import { useEffect, useState } from 'react'
import { api } from '../api'

export default function InstallAgent() {
  const [status, setStatus] = useState<{ registered: boolean; online: boolean } | null>(null)
  const [token, setToken] = useState('')
  const [err, setErr] = useState('')

  async function refresh() {
    try {
      setStatus(await api.get('/api/agent'))
    } catch (e: any) {
      setErr(e.message)
    }
  }
  useEffect(() => {
    refresh()
  }, [])

  async function generate() {
    setErr('')
    try {
      const { enrollment_token } = await api.post('/api/agent/install-token')
      setToken(enrollment_token)
    } catch (e: any) {
      setErr(e.message)
    }
  }

  return (
    <div className="max-w-2xl space-y-4">
      <h1 className="text-2xl font-bold text-white">Install Your Agent</h1>
      <p className="text-gray-400">
        The agent runs scans on your own machine and reports back. Install it once, then submit
        scans as normal.
      </p>
      {status && (
        <div className="card">
          Status:{' '}
          <span className={status.registered ? 'text-low' : 'text-med'}>
            {status.registered ? (status.online ? 'registered · online' : 'registered · offline') : 'not registered'}
          </span>
        </div>
      )}
      <button className="btn" onClick={generate}>
        Generate enrollment token
      </button>
      {token && (
        <div className="card space-y-2">
          <div className="text-sm text-gray-400">Run this once on your machine, then refresh:</div>
          <pre className="overflow-x-auto rounded bg-bg p-3 text-sm text-green-400">python agent.py {token}</pre>
          <button className="btn-ghost" onClick={refresh}>
            I've installed it, refresh
          </button>
        </div>
      )}
      {err && <div className="text-sm text-crit">{err}</div>}
    </div>
  )
}
