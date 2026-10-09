import { useState } from 'react'
import { createPortal } from 'react-dom'
import { changePassword } from '@/api'
import { useAuth } from '@/auth'
import { toast } from '@/lib/toast'
import { Button } from '@/components/ui/button'

const field = 'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const label = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'

// Self-service password change on the signed-in person's own plane (clients public, staff private).
// The server ends the old session and returns a new token, which changePassword() stores.
// - default: a dismissable dialog (account menus)
// - forced: the account carries a temporary password; no way out until it is changed
// - inline: the same form as a section of the Profile page
export function ChangePassword({ onClose, forced, inline }: { onClose: () => void; forced?: boolean; inline?: boolean }) {
  const { user } = useAuth()
  const [cur, setCur] = useState('')
  const [next, setNext] = useState('')
  const [again, setAgain] = useState('')
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  const id = inline ? 'chpw-inline' : 'chpw'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    if (next !== again) return setErr('The new passwords do not match.')
    if (next === cur) return setErr('Choose a password different from the current one.')
    setBusy(true)
    try {
      await changePassword(user?.role, cur, next)
      toast('Password changed.')
      setCur(''); setNext(''); setAgain('')
      onClose()
    } catch (e: any) {
      setErr(e.message || 'Could not change the password.')
    } finally {
      setBusy(false)
    }
  }

  const form = (
    <form
      onSubmit={submit}
      className={inline ? 'space-y-4' : 'w-full max-w-[400px] space-y-4 rounded-bento-lg border border-rule bg-card p-7 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]'}
      {...(inline ? { 'aria-labelledby': `${id}-title` } : { role: 'dialog', 'aria-modal': true, 'aria-labelledby': `${id}-title` })}
    >
      <h2 id={`${id}-title`} className={inline ? 'text-[15px] font-bold text-ink' : 'text-[18px] font-bold tracking-[-0.02em] text-ink'}>
        {forced ? 'Choose a new password' : 'Change password'}
      </h2>
      {forced && (
        <p className="text-[13px] leading-relaxed text-ink-muted">
          You signed in with a temporary password from your administrator. Pick your own password to continue.
        </p>
      )}
      <div><label htmlFor={`${id}-1`} className={label}>{forced ? 'Temporary password' : 'Current password'}</label><input id={`${id}-1`} className={field} type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} required autoFocus={!inline} /></div>
      <div><label htmlFor={`${id}-2`} className={label}>New password (8+ characters)</label><input id={`${id}-2`} className={field} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={8} /></div>
      <div><label htmlFor={`${id}-3`} className={label}>Repeat new password</label><input id={`${id}-3`} className={field} type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} required minLength={8} /></div>
      {err && <div role="alert" className="text-[12.5px] text-crit">{err}</div>}
      <div className="flex gap-2">
        {!forced && !inline && <Button type="button" variant="outline" className="min-h-[44px] flex-1" onClick={onClose}>Cancel</Button>}
        <Button type="submit" className={inline ? 'min-h-[44px]' : 'min-h-[44px] flex-1'} disabled={busy}>{inline ? 'Change password' : 'Save'}</Button>
      </div>
    </form>
  )

  if (inline) return form
  // Portal to <body>: the header it is opened from has filters/overflow that would otherwise
  // become the containing block for `fixed` and clip/offset the dialog.
  return createPortal(
    <div className="fixed inset-0 z-[60] grid place-items-center overflow-y-auto bg-shell/60 px-4 py-6" onKeyDown={(e) => !forced && e.key === 'Escape' && onClose()}>
      {form}
    </div>,
    document.body,
  )
}
