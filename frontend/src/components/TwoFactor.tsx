import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Copy, Check } from 'lucide-react'
import { api } from '@/api'
import { toast } from '@/lib/toast'
import { Button } from '@/components/ui/button'

const field = 'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const label = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'

// Two-factor (TOTP) for the signed-in team member: enrol with any authenticator app (Google/
// Microsoft Authenticator, Authy, 1Password), or turn it off again. No QR library on purpose:
// every app accepts the setup key typed in, and the otpauth link opens directly on a phone.
export function TwoFactor({ onClose }: { onClose: () => void }) {
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [setup, setSetup] = useState<{ secret: string; uri: string } | null>(null)
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => { api.pget('/api/mfa').then((r) => setEnabled(r.enabled)).catch(() => setEnabled(false)) }, [])

  const run = async (fn: () => Promise<void>) => {
    setErr('')
    try { await fn() } catch (e: any) { setErr(e.message || 'Something went wrong.') }
  }
  const begin = () => run(async () => setSetup(await api.ppost('/api/mfa/setup')))
  const enable = () => run(async () => { await api.ppost('/api/mfa/enable', { code }); setEnabled(true); setSetup(null); setCode(''); toast('Two-factor is on.') })
  const disable = () => run(async () => { await api.ppost('/api/mfa/disable', { password, code }); setEnabled(false); setCode(''); setPassword(''); toast('Two-factor is off.') })
  const copy = async () => { try { await navigator.clipboard.writeText(setup!.secret); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch {} }

  return createPortal(
    <div className="fixed inset-0 z-[60] grid place-items-center bg-shell/60 px-4" onKeyDown={(e) => e.key === 'Escape' && onClose()}>
      <div className="w-full max-w-[420px] space-y-4 rounded-bento-lg border border-rule bg-card p-7 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]" role="dialog" aria-label="Two-factor authentication">
        <h2 className="text-[18px] font-bold tracking-[-0.02em] text-ink">Two-factor authentication</h2>

        {enabled === null && <div className="text-[13px] text-ink-muted">Loading…</div>}

        {enabled === false && !setup && (
          <>
            <p className="text-[13px] leading-relaxed text-ink-muted">Adds a 6-digit code from your phone to every sign-in, so a stolen password alone can no longer open the team workspace.</p>
            <Button className="w-full" onClick={begin}>Set up</Button>
          </>
        )}

        {enabled === false && setup && (
          <>
            <ol className="list-decimal space-y-1.5 pl-5 text-[13px] leading-relaxed text-ink-muted">
              <li>In your authenticator app choose “Enter a setup key” and paste this key.</li>
              <li>Type the 6-digit code the app shows, then Turn on.</li>
            </ol>
            <div className="flex items-center gap-2 rounded-input border border-rule bg-panel px-3 py-2.5">
              <code className="min-w-0 flex-1 break-all font-mono text-[13px] tracking-wider text-ink" data-testid="mfa-secret">{setup.secret}</code>
              <button type="button" onClick={copy} aria-label="Copy key" className="text-ink-muted hover:text-ink">{copied ? <Check size={15} /> : <Copy size={15} />}</button>
            </div>
            <a href={setup.uri} className="block text-[12px] font-semibold text-accent">Open in authenticator app (on a phone)</a>
            <input className={field} inputMode="numeric" autoComplete="one-time-code" maxLength={6} placeholder="123456" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} />
            <Button className="w-full" disabled={code.length !== 6} onClick={enable}>Turn on</Button>
          </>
        )}

        {enabled === true && (
          <>
            <p className="text-[13px] font-semibold text-low">Two-factor is on for your account.</p>
            <p className="text-[12.5px] text-ink-muted">To turn it off, confirm your password and a current code.</p>
            <div><label className={label}>Password</label><input className={field} type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></div>
            <div><label className={label}>Code</label><input className={field} inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))} /></div>
            <Button variant="outline" className="w-full" disabled={!password || code.length !== 6} onClick={disable}>Turn off</Button>
          </>
        )}

        {err && <div className="text-[12.5px] text-crit">{err}</div>}
        <Button variant="outline" className="w-full" onClick={onClose}>Close</Button>
      </div>
    </div>,
    document.body,
  )
}
