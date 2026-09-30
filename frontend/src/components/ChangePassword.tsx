import { useState } from 'react'
import { api } from '@/api'
import { toast } from '@/lib/toast'
import { Button } from '@/components/ui/button'

const field = 'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const label = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'

// Self-service password change. `team` picks the plane: team accounts live on the private API,
// clients on the public one (the public plane refuses team tokens, NFR-24).
export function ChangePassword({ team, onClose }: { team?: boolean; onClose: () => void }) {
  const [cur, setCur] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    if (next !== again) return setErr('The new passwords do not match.')
    setBusy(true)
    try {
      await (team ? api.ppost : api.post)('/api/password', { current: cur, new: next })
      toast('Password changed.')
      onClose()
    } catch (e: any) {
      setErr(e.message || 'Could not change the password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-shell/60 px-4" onKeyDown={(e) => e.key === 'Escape' && onClose()}>
      <form onSubmit={submit} className="w-full max-w-[400px] space-y-4 rounded-bento-lg border border-rule bg-card p-7 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]" role="dialog" aria-label="Change password">
        <h2 className="text-[18px] font-bold tracking-[-0.02em] text-ink">Change password</h2>
        <div><label className={label}>Current password</label><input className={field} type="password" value={cur} onChange={(e) => setCur(e.target.value)} required autoFocus /></div>
        <div><label className={label}>New password (8+ characters)</label><input className={field} type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} /></div>
        <div><label className={label}>Repeat new password</label><input className={field} type="password" value={again} onChange={(e) => setAgain(e.target.value)} required minLength={8} /></div>
        {err && <div className="text-[12.5px] text-crit">{err}</div>}
        <div className="flex gap-2">
          <Button type="button" variant="outline" className="flex-1" onClick={onClose}>Cancel</Button>
          <Button type="submit" className="flex-1" disabled={busy}>Save</Button>
        </div>
      </form>
    </div>
  )
}
