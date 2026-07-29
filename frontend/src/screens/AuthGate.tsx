import { useEffect, useRef, useState } from 'react'
import anime from 'animejs'
import { Shield, Check, Clock, Terminal, Copy, ArrowRight, ShieldCheck } from 'lucide-react'
import { useAuth } from '@/auth'
import { api } from '@/api'
import { Button } from '@/components/ui/button'

type Step = 'auth' | 'proposal' | 'pending' | 'install'
const ONE_LINER =
  "$env:VARUNA_URL='https://<host>'; $env:VARUNA_TOKEN='<token>'; irm https://<host>/dist/install.ps1 | iex"

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

export function AuthGate({ onActivate }: { onActivate: () => void }) {
  const { login, register } = useAuth()
  const [step, setStep] = useState<Step>('auth')
  const [mode, setMode] = useState<'login' | 'register'>('register')
  const [u, setU] = useState('')
  const [p, setP] = useState('')
  const [target, setTarget] = useState('')
  const [attest, setAttest] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const cardRef = useRef<HTMLDivElement>(null)

  // Animate the card in on each step change (microinteraction).
  useEffect(() => {
    if (!cardRef.current) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    anime({ targets: cardRef.current, translateY: [16, 0], opacity: [0, 1], duration: 420, easing: 'easeOutCubic' })
  }, [step])

  async function submitAuth(e: React.FormEvent) {
    e.preventDefault()
    setErr('')
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(u, p)
        onActivate() // returning, already-onboarded user unlocks straight away
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

  async function submitProposal(e: React.FormEvent) {
    e.preventDefault()
    if (!attest) return
    setBusy(true)
    await api.post('/api/proposals', { target, authorization_attested: true })
    setBusy(false)
    setStep('pending')
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-shell/55 px-4 backdrop-blur-[2px]">
      <div
        ref={cardRef}
        className="w-full max-w-[440px] rounded-bento-lg border border-rule bg-card p-8 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)]"
      >
        {/* brand */}
        <div className="mb-6 flex items-center gap-2.5">
          <span
            className="grid h-9 w-9 place-items-center rounded-[11px]"
            style={{ background: 'conic-gradient(from 210deg,#F26A43,#f4996d,#F26A43)', boxShadow: 'inset 0 0 0 2px rgba(255,255,255,.14)' }}
          >
            <Shield size={19} className="fill-white text-white" />
          </span>
          <span className="text-[19px] font-bold tracking-[-0.02em] text-ink">Varuna</span>
        </div>

        {step === 'auth' && (
          <>
            <div className="mb-5 flex gap-1 rounded-pill bg-panel p-1">
              {(['register', 'login'] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`flex-1 rounded-pill py-2 text-[13.5px] font-semibold capitalize transition-colors ${
                    mode === m ? 'bg-card text-ink shadow-sm' : 'text-ink-muted'
                  }`}
                >
                  {m}
                </button>
              ))}
            </div>
            <form onSubmit={submitAuth} className="space-y-4">
              <div>
                <label className={label}>Username</label>
                <input className={field} value={u} onChange={(e) => setU(e.target.value)} placeholder="acme" required />
              </div>
              <div>
                <label className={label}>Password</label>
                <input className={field} type="password" value={p} onChange={(e) => setP(e.target.value)} placeholder="••••••••" required />
              </div>
              {err && <div className="text-[12.5px] text-crit">{err}</div>}
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                {mode === 'register' ? 'Create account' : 'Log in'} <ArrowRight size={16} />
              </Button>
              <p className="text-center text-[12px] leading-relaxed text-ink-muted">
                {mode === 'register'
                  ? 'Registering grants access only — the dashboard unlocks once a proposal is approved.'
                  : 'Welcome back.'}
              </p>
            </form>
          </>
        )}

        {step === 'proposal' && (
          <>
            <Stepper step={step} />
            <h2 className="text-[19px] font-bold tracking-[-0.02em] text-ink">Submit a scan proposal</h2>
            <p className="mb-5 mt-1 text-[13px] text-ink-muted">Your lead pentester approves this before any scan runs.</p>
            <form onSubmit={submitProposal} className="space-y-4">
              <div>
                <label className={label}>Target (in scope)</label>
                <input className={field} value={target} onChange={(e) => setTarget(e.target.value)} placeholder="https://api.acme.io" required />
              </div>
              <label className="flex cursor-pointer items-start gap-3 rounded-input border border-rule bg-panel p-3.5">
                <input type="checkbox" checked={attest} onChange={(e) => setAttest(e.target.checked)} className="mt-0.5 h-4 w-4 flex-none accent-[var(--color-accent)]" />
                <span className="text-[12.5px] leading-relaxed text-ink-muted">
                  I confirm I <b className="text-ink">own or am authorized</b> to test these assets. (Legally required — the lead verifies this.)
                </span>
              </label>
              <Button type="submit" size="lg" className="w-full" disabled={!attest || busy}>Submit for approval <ArrowRight size={16} /></Button>
            </form>
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
              <li className="flex items-center gap-2.5 text-[13px] text-ink-muted"><Clock size={16} className="text-accent" /> Pending lead-pentester approval…</li>
            </ul>
            <Button variant="outline" size="lg" className="w-full border-dashed" onClick={() => setStep('install')}>
              Demo · simulate lead approval <ArrowRight size={16} />
            </Button>
          </>
        )}

        {step === 'install' && (
          <>
            <Stepper step={step} />
            <div className="mb-4 flex items-center gap-3">
              <span className="grid h-11 w-11 flex-none place-items-center rounded-full bg-low-bg text-low"><ShieldCheck size={20} /></span>
              <div>
                <h2 className="text-[18px] font-bold tracking-[-0.02em] text-ink">Approved — install your agent</h2>
                <p className="text-[12.5px] text-ink-muted">Paste this in Windows PowerShell (no admin).</p>
              </div>
            </div>
            <div className="mb-5 rounded-input border border-rule bg-panel p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-ink-faint"><Terminal size={13} /> PowerShell</span>
                <button className="flex items-center gap-1.5 text-[11.5px] font-semibold text-ink-muted hover:text-ink"><Copy size={13} /> Copy</button>
              </div>
              <code className="block break-all font-mono text-[11.5px] leading-relaxed text-ink">{ONE_LINER}</code>
            </div>
            <Button size="lg" className="w-full" onClick={onActivate}>I've installed it — unlock <ArrowRight size={16} /></Button>
          </>
        )}
      </div>
    </div>
  )
}
