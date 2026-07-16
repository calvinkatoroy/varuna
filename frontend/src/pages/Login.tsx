import { useState } from 'react'
import { useAuth } from '../auth'

export default function Login() {
  const { login } = useAuth()
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await login(u, p)
    } catch (e: any) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={submit} className="card w-80 space-y-4">
        <h1 className="text-xl font-bold text-white">Varuna — Web VAPT</h1>
        <div>
          <label className="label">Username</label>
          <input className="input" value={u} onChange={(e) => setU(e.target.value)} autoFocus />
        </div>
        <div>
          <label className="label">Password</label>
          <input
            type="password"
            className="input"
            value={p}
            onChange={(e) => setP(e.target.value)}
          />
        </div>
        {err && <div className="text-sm text-crit">{err}</div>}
        <button className="btn w-full" disabled={busy}>
          {busy ? 'Signing in…' : 'Log in'}
        </button>
      </form>
    </div>
  )
}
