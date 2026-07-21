import { useState } from 'react'
import { useAuth } from '../auth'
import Button from '../components/Button'

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
    <div className="flex min-h-screen items-center justify-center bg-paper px-sm">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-md">
        <h1 className="font-display text-xl text-ink">Varuna: Web VAPT</h1>
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
        <Button busy={busy} busyLabel="Signing in…" className="w-full">
          Log in
        </Button>
      </form>
    </div>
  )
}
