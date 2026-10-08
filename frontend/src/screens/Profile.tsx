import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, LogIn, Mail, ShieldCheck, ShieldOff, XCircle } from 'lucide-react'
import { profile, type Profile as ProfileData } from '@/api'
import { useAuth } from '@/auth'
import { isMock } from '@/mock'
import { toast } from '@/lib/toast'
import { useApiData } from '@/lib/useApiData'
import { roleLabel } from '@/lib/roles'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/BrandMark'
import { ClientShell } from '@/components/ClientShell'
import { TeamAccount } from '@/components/TeamAccount'
import { ChangePassword } from '@/components/ChangePassword'
import { TwoFactor } from '@/components/TwoFactor'
import { ErrorRetry } from '@/components/ErrorRetry'

const field = 'min-h-[44px] w-full rounded-input border border-rule bg-panel px-3.5 py-2.5 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const lbl = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'
const card = 'rounded-bento bg-card p-5 sm:p-6'

// Where to go back to after signing in (a page that needs a session, like an email confirmation link).
export const RETURN_KEY = 'varuna-return'

// Shown on a signed-in-only page when nobody is signed in: remember this page, sign in, come back.
export function SignInFirst({ why }: { why: string }) {
  const { pathname, search } = useLocation()
  const navigate = useNavigate()
  const go = (to: string) => {
    try { sessionStorage.setItem(RETURN_KEY, pathname + search) } catch {}
    navigate(to)
  }
  return (
    <div className="grid min-h-screen place-items-center px-4">
      <div className="w-full max-w-[420px] space-y-4 rounded-bento-lg border border-rule bg-card p-8 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]">
        <div className="flex items-center gap-2.5"><BrandMark size={32} /><span className="text-[19px] font-bold tracking-[-0.02em] text-ink">Varuna</span></div>
        <h1 className="text-[18px] font-bold text-ink">Sign in to continue</h1>
        <p className="text-[13px] leading-relaxed text-ink-muted">{why} You will come straight back here after signing in.</p>
        <Button size="lg" className="w-full" onClick={() => go('/')}><LogIn size={16} /> Sign in</Button>
        <button type="button" onClick={() => go('/team')} className="block min-h-[44px] w-full text-center text-[13px] font-semibold text-accent-ink">Security team or administrator? Sign in on the team workspace</button>
      </div>
    </div>
  )
}

// Clients get the client frame (hero header + bottom dock on phones); staff and the system
// administrator get the plain private-plane header with their account menu.
function Frame({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  if (user?.role === 'client') return <ClientShell title="Profile" sub="Your account details and sign-in security.">{children}</ClientShell>
  const home = user?.role === 'sysadmin' ? '/team/sysadmin' : '/team'
  const homeName = user?.role === 'sysadmin' ? 'administration' : 'board'
  return (
    <div className="mx-auto max-w-[900px] p-[clamp(10px,2vw,28px)]">
      <a href="#main" className="sr-only rounded-pill bg-cta-bg px-4 py-2 text-[13px] font-semibold text-cta-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:px-5 focus:py-3 focus:shadow-lg">Skip to content</a>
      <header className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-bento-lg bg-card px-5 py-3.5 sm:px-6">
        <Link to={home} aria-label={`Back to the ${homeName}`} className="-ml-2 grid h-11 w-11 place-items-center rounded-full text-ink-muted hover:text-ink sm:hidden"><ArrowLeft size={20} /></Link>
        <Link to={home} className="hidden items-center gap-2.5 text-[18px] font-bold tracking-[-0.02em] text-ink sm:flex"><BrandMark size={28} /> Varuna</Link>
        <h1 className="text-[18px] font-bold text-ink">Profile</h1>
        <div className="ml-auto flex items-center gap-3">
          <Link to={home} className="hidden min-h-[44px] items-center text-[13px] font-semibold text-accent-ink sm:inline-flex">Back to {homeName}</Link>
          <TeamAccount />
        </div>
      </header>
      <main id="main" tabIndex={-1} className="focus:outline-none">{children}</main>
    </div>
  )
}

function Details({ p, onSaved }: { p: ProfileData; onSaved: () => void }) {
  const { user } = useAuth()
  const [name, setName] = useState(p.display_name ?? '')
  const [phone, setPhone] = useState(p.phone ?? '')
  const [busy, setBusy] = useState(false)
  const dirty = name !== (p.display_name ?? '') || phone !== (p.phone ?? '')
  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try { await profile.update(user?.role, { display_name: name.trim(), phone: phone.trim() }); toast('Profile saved.'); onSaved() } catch {} finally { setBusy(false) }
  }
  return (
    <form onSubmit={save} className={card} aria-labelledby="pf-details">
      <h2 id="pf-details" className="mb-4 text-[15px] font-bold text-ink">Your details</h2>
      <div className="grid gap-4 sm:grid-cols-2">
        <div><label htmlFor="pf-name" className={lbl}>Display name</label><input id="pf-name" className={field} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} autoComplete="name" placeholder="Siti Nurhaliza" /></div>
        <div><label htmlFor="pf-phone" className={lbl}>Phone</label><input id="pf-phone" className={field} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={40} autoComplete="tel" placeholder="+62 812 3456 7890" /></div>
      </div>
      <Button type="submit" className="mt-4" disabled={busy || !dirty}>Save details</Button>
    </form>
  )
}

function Email({ p }: { p: ProfileData }) {
  const { user } = useAuth()
  const [email, setEmail] = useState('')
  const [busy, setBusy] = useState(false)
  const [sent, setSent] = useState<{ to: string; emailed: boolean } | null>(null)
  const send = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const to = email.trim()
      const r = await profile.requestEmail(user?.role, to)
      setSent({ to, emailed: r.emailed })
      setEmail('')
    } catch {} finally { setBusy(false) }
  }
  return (
    <form onSubmit={send} className={card} aria-labelledby="pf-email">
      <h2 id="pf-email" className="mb-1 text-[15px] font-bold text-ink">Email</h2>
      <p className="mb-4 text-[13px] text-ink-muted">Current address: <span className="break-all font-semibold text-ink">{p.email || 'none on file'}</span></p>
      <label htmlFor="pf-newemail" className={lbl}>New email address</label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input id="pf-newemail" className={field} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" placeholder="nama@perusahaan.co.id" />
        <Button type="submit" className="flex-none" disabled={busy}><Mail size={15} /> Send confirmation link</Button>
      </div>
      <p className="mt-3 text-[12.5px] leading-relaxed text-ink-muted">
        Your address changes only after you open the link we send to the new address. The link works for 30 minutes, while you are signed in as yourself.
      </p>
      {sent && (
        <p role="status" className={`mt-3 rounded-input p-3 text-[12.5px] leading-relaxed ${sent.emailed ? 'bg-low-bg text-ink' : 'bg-med-bg text-ink'}`}>
          {sent.emailed
            ? <>Link sent to <b className="break-all">{sent.to}</b>. Open it to finish the change. Check your spam folder if it does not arrive.</>
            : <>Email is not configured on this server, so no link was sent and your address has not changed. Contact your administrator to update it.</>}
        </p>
      )}
    </form>
  )
}

export default function Profile() {
  const { user } = useAuth()
  const { data: p, error, reload } = useApiData<ProfileData>(() => profile.get(user?.role))
  const [tf, setTf] = useState(false)
  const staff = user?.role !== 'client'

  return (
    <Frame>
      {error ? <ErrorRetry message={error} onRetry={reload} /> : !p ? <div className="p-6 text-[13px] text-ink-muted">Loading…</div> : (
        <div className="grid gap-3.5">
          <section className={card} aria-labelledby="pf-account">
            <h2 id="pf-account" className="mb-3 text-[15px] font-bold text-ink">Account</h2>
            <dl className="grid gap-x-6 gap-y-3 text-[13.5px] sm:grid-cols-3">
              <div><dt className="text-[12.5px] text-ink-muted">Username</dt><dd className="break-all font-semibold text-ink">{p.username}</dd></div>
              <div><dt className="text-[12.5px] text-ink-muted">Role</dt><dd className="font-semibold text-ink">{roleLabel(p.role)}</dd></div>
              <div><dt className="text-[12.5px] text-ink-muted">Organization</dt><dd className="break-words font-semibold text-ink">{p.org_name || (staff ? 'Varuna staff' : 'None')}</dd></div>
            </dl>
            <p className="mt-3 text-[12px] text-ink-muted">Username, role and organization are managed by your administrator.</p>
          </section>

          {/* keyed so the form picks up the saved values after a reload */}
          <Details key={`${p.display_name}|${p.phone}`} p={p} onSaved={reload} />
          <Email p={p} />

          <section className={card}>
            <ChangePassword inline onClose={() => {}} />
          </section>

          {/* Two-factor exists on the private plane only (staff and the system administrator). */}
          {staff && (
            <section className={card} aria-labelledby="pf-2fa">
              <h2 id="pf-2fa" className="mb-2 text-[15px] font-bold text-ink">Two-factor authentication</h2>
              <p className="mb-4 flex items-center gap-2 text-[13px] text-ink">
                {p.totp_enabled
                  ? <><ShieldCheck size={16} className="text-low" /> On: sign-in asks for a code from your authenticator app.</>
                  : <><ShieldOff size={16} className="text-ink-muted" /> Off: a password alone opens your account.</>}
              </p>
              <Button variant="outline" onClick={() => setTf(true)}>{p.totp_enabled ? 'Manage two-factor' : 'Set up two-factor'}</Button>
              {tf && <TwoFactor onClose={() => { setTf(false); reload() }} />}
            </section>
          )}
        </div>
      )}
    </Frame>
  )
}

// /confirm-email?token=... (the link mailed by POST /api/profile/email). Needs the same person
// signed in; confirms once (a ref guards React strict mode's double effect), then points to the profile.
export function ConfirmEmail() {
  const { user } = useAuth()
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  const started = useRef(false)
  const [state, setState] = useState<'working' | 'ok' | 'failed'>(token ? 'working' : 'failed')
  const [msg, setMsg] = useState(token ? '' : 'This link has no confirmation code. Open the link from the email again.')

  useEffect(() => {
    // Wait for a signed-in user who is past any forced password change, then confirm exactly once.
    if (!token || !user || user.must_change_password || started.current) return
    started.current = true
    profile.confirmEmail(user.role, token)
      .then(() => setState('ok'))
      .catch((e) => {
        setState('failed')
        setMsg(e?.status === 422 || !e?.message ? 'This link is invalid, was already used, or has expired.' : e.message)
      })
  }, [token, user])

  return (
    <Frame>
      <section className={`${card} mx-auto max-w-[520px] text-center`} aria-live="polite">
        {state === 'working' && <p className="py-6 text-[13.5px] text-ink-muted">Confirming your new email address…</p>}
        {state === 'ok' && (
          <>
            <CheckCircle2 size={36} className="mx-auto mb-3 text-low" aria-hidden />
            <h2 className="text-[18px] font-bold text-ink">Email confirmed</h2>
            <p className="mt-1 text-[13px] text-ink-muted">Your account now uses the new address.</p>
          </>
        )}
        {state === 'failed' && (
          <>
            <XCircle size={36} className="mx-auto mb-3 text-crit" aria-hidden />
            <h2 className="text-[18px] font-bold text-ink">Could not confirm the email</h2>
            <p className="mt-1 text-[13px] text-ink-muted">{msg} You can request a new link from your profile.</p>
          </>
        )}
        {state !== 'working' && <Button asChild className="mt-5"><Link to="/profile">Go to your profile</Link></Button>}
      </section>
    </Frame>
  )
}

// /profile and /confirm-email: any signed-in role on either plane. Mock mode signs in as the demo client.
export function SignedInRoute({ children, why }: { children: React.ReactNode; why: string }) {
  const { user, login } = useAuth()
  useEffect(() => {
    if (isMock() && !user) login('samudera', '').catch(() => {})
  }, [user, login])
  if (!user) return isMock() ? null : <SignInFirst why={why} />
  return <>{children}</>
}
