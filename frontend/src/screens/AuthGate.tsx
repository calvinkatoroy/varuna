import { useEffect, useRef, useState } from 'react'
import anime from 'animejs'
import { Check, Clock, Terminal, Copy, ArrowRight, ShieldCheck, Download } from 'lucide-react'
import { useAuth } from '@/auth'
import { api, download } from '@/api'
import { isMock } from '@/mock'
import { Button } from '@/components/ui/button'
import { ProposalForm } from '@/components/ProposalForm'
import { BrandMark } from '@/components/BrandMark'

// /api/proposals speaks the client vocabulary: anything past pending/rejected was approved.
const isApproved = (x: { status: string }) => x.status !== 'pending' && x.status !== 'rejected'
const isCloud = (x: { scan_mode?: string }) => x.scan_mode === 'cloud'

type Step = 'auth' | 'proposal' | 'pending' | 'install'
const oneLiner = (host: string, token: string) =>
  `$env:VARUNA_URL='${host}'; $env:VARUNA_TOKEN='${token}'; irm ${host}/dist/install.ps1 | iex`

const field =
  'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const label = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'

function Stepper({ step }: { step: Step }) {
  const steps = ['Account', 'Proposal', 'Approval', 'Agent']
  const idx = { auth: 0, proposal: 1, pending: 2, install: 3 }[step]
  return (
    <div className="mb-6 flex items-center gap-2">
      {steps.map((s, i) => (
        <div key={s} className="flex flex-1 items-center gap-2">
          <div className="flex items-center gap-2">
            <span
              className={`grid h-6 w-6 flex-none place-items-center rounded-full text-[11px] font-bold ${
                i < idx ? 'bg-low text-white' : i === idx ? 'bg-accent text-white' : 'bg-panel text-ink-faint'
              }`}
            >
              {i < idx ? <Check size={13} /> : i + 1}
            </span>
            <span className={`text-[12px] font-medium ${i <= idx ? 'text-ink' : 'text-ink-faint'} ${i === idx ? '' : 'hidden sm:inline'}`}>{s}</span>
          </div>
          {i < steps.length - 1 && <span className="h-px flex-1 bg-rule" />}
        </div>
      ))}
    </div>
  )
}

export function AuthGate({ onActivate }: { onActivate: (username: string) => void }) {
  const { login, user } = useAuth()
  const [step, setStep] = useState<Step>('auth')
  const [u, setU] = useState('')
  const [email, setEmail] = useState('')
  const [forgot, setForgot] = useState<'' | 'form' | 'sent'>('')
  const [p, setP] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  // Set when every proposal so far was rejected: the client must see why, and can try again.
  const [notice, setNotice] = useState('')
  const [copied, setCopied] = useState(false)
  const [enrollToken, setEnrollToken] = useState('')
  const cardRef = useRef<HTMLDivElement>(null)
  const oneLinerText = oneLiner(api.publicBase || window.location.origin, enrollToken || '<fetching…>')

  // A real one-time enrollment token (POST /api/agent/install-token), not a placeholder -
  // fetched once we actually reach the install step.
  useEffect(() => {
    if (step !== 'install') return
    api.post('/api/agent/install-token').then((r) => setEnrollToken(r.enrollment_token)).catch(() => {})
  }, [step])

  const copyOneLiner = async () => {
    try { await navigator.clipboard.writeText(oneLinerText); setCopied(true); setTimeout(() => setCopied(false), 1600) } catch {}
  }

  // On the install step, notice the agent coming online by itself: a non-technical person should not have to
  // know to come back and press a button.
  useEffect(() => {
    if (step !== 'install' || isMock()) return
    const t = setInterval(() => {
      api.get('/api/agent').then((a: { registered: boolean }) => { if (a.registered) onActivate(user?.username || u) }).catch(() => {})
    }, 4000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step])

  const [dl, setDl] = useState(false)
  const getInstaller = async () => {
    setErr('')
    try { await download(api.publicBase, '/api/agent/installer', 'Install-Varuna.cmd'); setDl(true) } catch (e: any) { setErr(e.message || 'Could not download the installer.') }
  }

  // Animate the card in on each step change (microinteraction).
  useEffect(() => {
    if (!cardRef.current) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    anime({ targets: cardRef.current, translateY: [16, 0], opacity: [0, 1], duration: 420, easing: 'easeOutCubic' })
  }, [step])

  // Where a returning user actually is in onboarding, decided by the server, not assumed.
  async function resumeFlow(username: string) {
    const props: { status: string; reason?: string; scan_mode?: string }[] = await api.get('/api/proposals')
    if (!props.length) return setStep('proposal')
    if (!props.some(isApproved) && !props.some((x) => x.status === 'pending')) {
      const last = props.find((x) => x.status === 'rejected')
      setNotice(`Your last proposal was not approved${last?.reason ? `: ${last.reason}` : '.'} Fix what they asked for and submit a new one.`)
      return setStep('proposal')
    }
    if (!props.some(isApproved)) return setStep('pending')
    if (props.filter(isApproved).every(isCloud)) return onActivate(username)   // Varuna runs the scan: no agent to install
    const agent = await api.get('/api/agent')
    if (agent.registered) onActivate(username)
    else setStep('install')
  }

  // Already signed in (page reloaded, tab reopened mid-onboarding): pick up where they left off
  // instead of showing the login form to someone who has an account.
  useEffect(() => {
    if (user?.role === 'client' && step === 'auth' && !isMock()) resumeFlow(user.username).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.username])

  // Waiting on the lead pentester: check for approval instead of trusting a button.
  useEffect(() => {
    if (step !== 'pending' || isMock()) return
    const t = setInterval(() => {
      api.get('/api/proposals').then((ps: { status: string; reason?: string; scan_mode?: string }[]) => {
        if (ps.some(isApproved)) return ps.filter(isApproved).every(isCloud) ? onActivate(user?.username || u) : setStep('install')
        if (ps.length && !ps.some((x) => x.status === 'pending')) {   // decided against: show why, allow a retry
          const last = ps.find((x) => x.status === 'rejected')
          setNotice(`Your proposal was not approved${last?.reason ? `: ${last.reason}` : '.'} Fix what they asked for and submit a new one.`)
          setStep('proposal')
        }
      }).catch(() => {})
    }, 5000)
    return () => clearInterval(t)
  }, [step])

  async function unlock() {
    setErr('')
    try {
      const agent = await api.get('/api/agent')
      if (!agent.registered) return setErr('Agent not detected yet. Run the command above, then try again.')
      onActivate(user?.username || u)
    } catch (e: any) { setErr(e.message || 'failed') }
  }

  async function submitAuth(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      await login(u, p)
      await resumeFlow(u)
    } catch (e: any) {
      setErr(e.message || 'failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-shell/55 px-4 backdrop-blur-[2px]">
      <div
        ref={cardRef}
        role="dialog" aria-modal="true" aria-label="Sign in to Varuna"
        className={`w-full min-w-0 ${step === 'proposal' ? 'max-w-[600px]' : 'max-w-[440px]'} rounded-bento-lg border border-rule bg-card p-8 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]`}
      >
        {/* brand */}
        <div className="mb-6 flex items-center gap-2.5">
          <BrandMark size={36} />
          <span className="text-[19px] font-bold tracking-[-0.02em] text-ink">Varuna</span>
        </div>

        {step === 'auth' && (
          <>
            {forgot ? (
              <form
                className="space-y-4"
                onSubmit={async (e) => {
                  e.preventDefault()
                  setBusy(true)
                  try { await api.post('/api/password-reset/request', { email: email.trim() }); setForgot('sent') } catch {} finally { setBusy(false) }
                }}
              >
                {forgot === 'sent' ? (
                  <p role="status" className="text-[13px] leading-relaxed text-ink-muted">If that address is registered, a reset link is on its way. It works for 30 minutes. Check your spam folder if it does not arrive.</p>
                ) : (
                  <>
                    <p className="text-[13px] leading-relaxed text-ink-muted">Enter the email you registered with and we will send a reset link. No email on file? Ask your lead pentester.</p>
                    <div>
                      <label htmlFor="auth-4" className={label}>Email</label>
                      <input id="auth-4" className={field} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
                    </div>
                    <Button type="submit" size="lg" className="w-full" disabled={busy}>Send reset link</Button>
                  </>
                )}
                <button type="button" onClick={() => setForgot('')} className="block min-h-[44px] w-full text-center text-[13px] font-semibold text-accent-ink">Back to log in</button>
              </form>
            ) : (
            <form onSubmit={submitAuth} className="space-y-4">
              <div>
                <label htmlFor="auth-1" className={label}>Username</label>
                <input id="auth-1" className={field} autoCapitalize="none" autoCorrect="off" spellCheck={false} value={u} onChange={(e) => setU(e.target.value)} placeholder="acme" required />
              </div>
              <div>
                <label htmlFor="auth-2" className={label}>Password</label>
                <input id="auth-2" className={field} type="password" value={p} onChange={(e) => setP(e.target.value)} placeholder="••••••••" required />
              </div>
              {err && <div className="text-[12.5px] text-crit">{err}</div>}
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                Log in <ArrowRight size={16} />
              </Button>
              <button type="button" onClick={() => setForgot('form')} className="block min-h-[44px] w-full text-center text-[13px] font-semibold text-accent-ink">Forgot your password?</button>
              <p className="text-center text-[12px] leading-relaxed text-ink-muted">Accounts are created by your administrator.</p>
            </form>
            )}
          </>
        )}

        {step === 'proposal' && (
          <>
            <Stepper step={step} />
            <h2 className="text-[19px] font-bold tracking-[-0.02em] text-ink">Submit a scan proposal</h2>
            {notice && <p role="status" className="mb-2 mt-2 rounded-input border border-crit-bg bg-crit-bg p-3 text-[13px] leading-relaxed text-crit">{notice}</p>}
            <p className="mb-4 mt-1 text-[13px] text-ink-muted">Your lead pentester verifies this before any scan runs.</p>
            <div className="max-h-[58vh] overflow-y-auto pr-1">
              <ProposalForm
                submitLabel="Submit for approval"
                onSubmit={async (payload) => {
                  await api.post('/api/proposals', payload)
                  setStep('pending')
                }}
              />
            </div>
          </>
        )}

        {step === 'pending' && (
          <>
            <Stepper step={step} />
            <div className="mb-4 flex items-center gap-3">
              <span className="grid h-11 w-11 flex-none place-items-center rounded-full bg-accent-soft text-accent-ink"><Clock size={20} /></span>
              <div>
                <h2 className="text-[18px] font-bold tracking-[-0.02em] text-ink">Awaiting approval</h2>
                <p className="text-[12.5px] text-ink-muted">Your lead pentester is reviewing the proposal.</p>
              </div>
            </div>
            <ul className="mb-6 space-y-2.5">
              <li className="flex items-center gap-2.5 text-[13px] text-ink"><Check size={16} className="text-low" /> Account created</li>
              <li className="flex items-center gap-2.5 text-[13px] text-ink"><Check size={16} className="text-low" /> Proposal submitted</li>
              <li className="flex items-center gap-2.5 text-[13px] text-ink-muted"><Clock size={16} className="text-accent-ink" /> Pending lead-pentester approval…</li>
            </ul>
            {isMock() && (
              <Button variant="outline" size="lg" className="w-full border-dashed" onClick={() => setStep('install')}>
                Demo · simulate lead approval <ArrowRight size={16} />
              </Button>
            )}
          </>
        )}

        {step === 'install' && (
          <>
            <Stepper step={step} />
            <div className="mb-4 flex items-center gap-3">
              <span className="grid h-11 w-11 flex-none place-items-center rounded-full bg-low-bg text-low"><ShieldCheck size={20} /></span>
              <div>
                <h2 className="text-[18px] font-bold tracking-[-0.02em] text-ink">Approved. Install your agent</h2>
                <p className="text-[12.5px] text-ink-muted">One small program on your Windows computer runs the scan. No admin rights needed.</p>
              </div>
            </div>
            <Button size="lg" className="w-full" onClick={getInstaller}><Download size={16} /> Download installer (Windows)</Button>
            <ol className="mb-5 mt-4 list-decimal space-y-1.5 pl-5 text-[13px] leading-relaxed text-ink-muted">
              <li>Open the downloaded file <b className="text-ink">Install-Varuna</b> (double-click it).</li>
              <li>If Windows says <b className="text-ink">"Windows protected your PC"</b>, click <b className="text-ink">More info</b>, then <b className="text-ink">Run anyway</b>.</li>
              <li>Wait a few minutes for "Done". This page unlocks by itself.</li>
            </ol>
            {dl && <p role="status" className="mb-4 rounded-input bg-low-bg p-3 text-[12.5px] text-low">Downloaded. The installer works for one hour. If it stops working, download it again.</p>}
            <details className="mb-5 rounded-input border border-rule bg-panel p-3">
              <summary className="min-h-[44px] cursor-pointer text-[12.5px] font-semibold text-ink-muted">I'd rather use PowerShell</summary>
              <div className="mt-2">
              <div className="mb-2 flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-faint"><Terminal size={13} /> PowerShell</span>
                <button onClick={copyOneLiner} className="flex items-center gap-1.5 text-[11.5px] font-semibold text-ink-muted hover:text-ink">{copied ? <><Check size={13} className="text-low" /> Copied</> : <><Copy size={13} /> Copy</>}</button>
              </div>
              <code className="block break-all font-mono text-[11.5px] leading-relaxed text-ink">{oneLinerText}</code>
              </div>
            </details>
            {err && <div className="mb-3 text-[12.5px] text-crit">{err}</div>}
            <Button size="lg" className="w-full" onClick={unlock}>I've installed it. Check now <ArrowRight size={16} /></Button>
          </>
        )}
      </div>
    </div>
  )
}
