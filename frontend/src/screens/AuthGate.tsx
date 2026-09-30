import { useEffect, useRef, useState } from 'react'
import anime from 'animejs'
import { Check, Clock, Terminal, Copy, ArrowRight, ShieldCheck } from 'lucide-react'
import { useAuth } from '@/auth'
import { api } from '@/api'
import { isMock } from '@/mock'
import { Button } from '@/components/ui/button'
import { ProposalForm } from '@/components/ProposalForm'
import { BrandMark } from '@/components/BrandMark'

// /api/proposals speaks the client vocabulary: anything past pending/rejected was approved.
const isApproved = (x: { status: string }) => x.status !== 'pending' && x.status !== 'rejected'

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
            <span className={`text-[12px] font-medium ${i <= idx ? 'text-ink' : 'text-ink-faint'}`}>{s}</span>
          </div>
          {i < steps.length - 1 && <span className="h-px flex-1 bg-rule" />}
        </div>
      ))}
    </div>
  )
}

export function AuthGate({ onActivate }: { onActivate: (username: string) => void }) {
  const { login, register, user } = useAuth()
  const [step, setStep] = useState<Step>('auth')
  const [mode, setMode] = useState<'login' | 'register'>('register')
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
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

  // Animate the card in on each step change (microinteraction).
  useEffect(() => {
    if (!cardRef.current) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    anime({ targets: cardRef.current, translateY: [16, 0], opacity: [0, 1], duration: 420, easing: 'easeOutCubic' })
  }, [step])

  // Where a returning user actually is in onboarding, decided by the server, not assumed.
  async function resumeFlow(username: string) {
    const props: { status: string }[] = await api.get('/api/proposals')
    if (!props.length) return setStep('proposal')
    if (!props.some(isApproved)) return setStep('pending')
    const agent = await api.get('/api/agent')
    if (agent.registered) onActivate(username)
    else setStep('install')
  }

  // Waiting on the lead pentester: check for approval instead of trusting a button.
  useEffect(() => {
    if (step !== 'pending' || isMock()) return
    const t = setInterval(() => {
      api.get('/api/proposals').then((ps: { status: string }[]) => {
        if (ps.some(isApproved)) setStep('install')
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
      if (mode === 'login') {
        await login(u, p)
        await resumeFlow(u)
      } else {
        await register(u, p)
        setStep('proposal')
      }
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
        className={`w-full ${step === 'proposal' ? 'max-w-[600px]' : 'max-w-[440px]'} rounded-bento-lg border border-rule bg-card p-8 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]`}
      >
        {/* brand */}
        <div className="mb-6 flex items-center gap-2.5">
          <BrandMark size={36} />
          <span className="text-[19px] font-bold tracking-[-0.02em] text-ink">Varuna</span>
        </div>

        {step === 'auth' && (
          <>
            <div className="mb-5 flex gap-1 rounded-pill bg-panel p-1">
              {(['register', 'login'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`min-h-[44px] flex-1 rounded-pill py-2 text-[13.5px] font-semibold capitalize transition-colors ${
                    mode === m ? 'bg-card text-ink shadow-sm' : 'text-ink-muted'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
            <form onSubmit={submitAuth} className="space-y-4">
              <div>
                <label htmlFor="auth-1" className={label}>Username</label>
                <input id="auth-1" className={field} value={u} onChange={(e) => setU(e.target.value)} placeholder="acme" required />
              </div>
              <div>
                <label htmlFor="auth-2" className={label}>Password</label>
                <input id="auth-2" className={field} type="password" value={p} onChange={(e) => setP(e.target.value)} placeholder="••••••••" required />
              </div>
              {err && <div className="text-[12.5px] text-crit">{err}</div>}
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                {mode === 'register' ? 'Create account' : 'Log in'} <ArrowRight size={16} />
              </Button>
              <p className="text-center text-[12px] leading-relaxed text-ink-muted">
                {mode === 'register'
                  ? 'Registering grants access only. The dashboard unlocks once a proposal is approved.'
                  : 'Welcome back.'}
              </p>
            </form>
          </>
        )}

        {step === 'proposal' && (
          <>
            <Stepper step={step} />
            <h2 className="text-[19px] font-bold tracking-[-0.02em] text-ink">Submit a scan proposal</h2>
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
                <p className="text-[12.5px] text-ink-muted">Paste this in Windows PowerShell (no admin).</p>
              </div>
            </div>
            <div className="mb-5 rounded-input border border-rule bg-panel p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-faint"><Terminal size={13} /> PowerShell</span>
                <button onClick={copyOneLiner} className="flex items-center gap-1.5 text-[11.5px] font-semibold text-ink-muted hover:text-ink">{copied ? <><Check size={13} className="text-low" /> Copied</> : <><Copy size={13} /> Copy</>}</button>
              </div>
              <code className="block break-all font-mono text-[11.5px] leading-relaxed text-ink">{oneLinerText}</code>
            </div>
            {err && <div className="mb-3 text-[12.5px] text-crit">{err}</div>}
            <Button size="lg" className="w-full" onClick={unlock}>I've installed it. Unlock <ArrowRight size={16} /></Button>
          </>
        )}
      </div>
    </div>
  )
}
