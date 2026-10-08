import { useState } from 'react'
import { ArrowRight, Lock } from 'lucide-react'
import { useAuth } from '@/auth'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/BrandMark'

const field = 'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const label = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'

// Staff and system administrator accounts are provisioned by the system administrator, so this is
// login-only, unlike the client AuthGate's login -> proposal -> approval -> agent flow. Gates every
// /team route (see App.tsx's RoleRoute): a client account logging in here just gets told it
// doesn't have team access, rather than the frontend silently rendering the private plane to
// whoever navigates to the URL.
export function TeamLogin() {
  const { login } = useAuth()
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [needCode, setNeedCode] = useState(false)
  const [code, setCode] = useState('')

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await login(u, p, true, code || undefined)
    } catch (e: any) {
      if (e.message === 'mfa_required') { setNeedCode(true); setErr('Enter the 6-digit code from your authenticator app.') }
      else setErr(e.message || 'failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-shell/55 px-4 backdrop-blur-[2px]">
      <div role="dialog" aria-modal="true" aria-label="Team sign in" className="w-full max-w-[400px] rounded-bento-lg border border-rule bg-card p-8 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]">
        <div className="mb-6 flex items-center gap-2.5">
          <BrandMark size={36} />
          <span className="text-[19px] font-bold tracking-[-0.02em] text-ink">Varuna</span>
        </div>
        <div className="mb-5 flex items-center gap-2 text-[12.5px] text-ink-muted"><Lock size={13} /> Private plane · security team only</div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label htmlFor="team-login-1" className={label}>Username</label>
            <input id="team-login-1" className={field} autoCapitalize="none" autoCorrect="off" spellCheck={false} value={u} onChange={(e) => setU(e.target.value)} placeholder="admin" required autoFocus />
          </div>
          <div>
            <label htmlFor="team-login-2" className={label}>Password</label>
            <input id="team-login-2" className={field} type="password" value={p} onChange={(e) => setP(e.target.value)} placeholder="••••••••" required />
          </div>
          {needCode && (
            <div>
              <label htmlFor="team-login-3" className={label}>Authenticator code</label>
              <input id="team-login-3" className={field} inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} placeholder="123456" required autoFocus />
            </div>
          )}
          {err && <div className="text-[12.5px] text-crit">{err}</div>}
          <Button type="submit" size="lg" className="w-full" disabled={busy}>Log in <ArrowRight size={16} /></Button>
        </form>
      </div>
    </div>
  )
}
