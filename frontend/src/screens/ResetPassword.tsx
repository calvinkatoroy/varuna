import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Check } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/BrandMark'

const field = 'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const label = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'

// Landing page of the emailed reset link (/reset?token=...). Outside the client gate on purpose:
// the person cannot log in, which is the whole point.
export default function ResetPassword() {
  const token = useSearchParams()[0].get('token') ?? ''
  const [pw, setPw] = useState('')
  const [again, setAgain] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (pw !== again) return setErr('The two passwords are not the same.')
    setErr('')
    setBusy(true)
    try {
      await api.post('/api/password-reset/confirm', { token, new: pw })
      setDone(true)
    } catch (e: any) {
      setErr(e.message || 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-screen place-items-center bg-shell px-4">
      <div className="w-full max-w-[420px] rounded-bento-lg border border-rule bg-card p-8 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]">
        <div className="mb-6 flex items-center gap-2.5">
          <BrandMark size={36} />
          <span className="text-[19px] font-bold tracking-[-0.02em] text-ink">Varuna</span>
        </div>
        {done ? (
          <div className="space-y-4" role="status">
            <div className="flex items-center gap-2 text-[15px] font-semibold text-low"><Check size={18} /> Password changed</div>
            <p className="text-[13px] text-ink-muted">You can log in with the new password now.</p>
            <Link to="/" className="block"><Button className="w-full">Go to log in</Button></Link>
          </div>
        ) : !token ? (
          <p className="text-[13px] text-ink-muted">This link is incomplete. Open the link from the email again, or request a new one from the log in screen.</p>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <h1 className="text-[18px] font-bold tracking-[-0.02em] text-ink">Choose a new password</h1>
            <div>
              <label htmlFor="reset-1" className={label}>New password (at least 8 characters)</label>
              <input id="reset-1" className={field} type="password" autoComplete="new-password" value={pw} onChange={(e) => setPw(e.target.value)} required minLength={8} autoFocus />
            </div>
            <div>
              <label htmlFor="reset-2" className={label}>Type it again</label>
              <input id="reset-2" className={field} type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} required />
            </div>
            {err && <div role="alert" className="text-[12.5px] text-crit">{err}</div>}
            <Button type="submit" size="lg" className="w-full" disabled={busy}>Change password</Button>
          </form>
        )}
      </div>
    </div>
  )
}
