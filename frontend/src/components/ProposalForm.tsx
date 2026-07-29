import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

const field = 'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const label = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'

export type ProposalPayload = {
  target: string; in_scope: string; out_of_scope: string; purpose: string; division: string
  environment: string; test_window: string; roe: { authenticated: boolean; credentials: string; dos_allowed: boolean }
  authorization_attested: true
}

// The scan-proposal scoping form, shared by the onboarding gate and the in-app "New Proposal".
export function ProposalForm({ onSubmit, submitLabel = 'Submit for approval' }: { onSubmit: (p: ProposalPayload) => Promise<void> | void; submitLabel?: string }) {
  const [target, setTarget] = useState('')
  const [outScope, setOutScope] = useState('')
  const [purpose, setPurpose] = useState('pre-release')
  const [division, setDivision] = useState('')
  const [environment, setEnvironment] = useState('production')
  const [testWindow, setTestWindow] = useState('')
  const [authed, setAuthed] = useState(false)
  const [creds, setCreds] = useState('')
  const [dos, setDos] = useState(false)
  const [attest, setAttest] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!attest) return
    setBusy(true)
    await onSubmit({
      target, in_scope: target, out_of_scope: outScope, purpose, division, environment,
      test_window: testWindow, roe: { authenticated: authed, credentials: creds, dos_allowed: dos },
      authorization_attested: true,
    })
    setBusy(false)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label className={label}>In-scope target(s)</label>
        <input className={field} value={target} onChange={(e) => setTarget(e.target.value)} placeholder="https://api.acme.io" required />
      </div>
      <div>
        <label className={label}>Out of scope <span className="text-ink-faint">(optional)</span></label>
        <input className={field} value={outScope} onChange={(e) => setOutScope(e.target.value)} placeholder="admin.acme.io, /billing" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={label}>Purpose (keperluan)</label>
          <select className={field} value={purpose} onChange={(e) => setPurpose(e.target.value)}>
            <option value="pre-release">Pre-release</option>
            <option value="compliance">Compliance (ISO/PCI)</option>
            <option value="periodic">Periodic</option>
            <option value="incident">Incident-driven</option>
          </select>
        </div>
        <div>
          <label className={label}>Division</label>
          <input className={field} value={division} onChange={(e) => setDivision(e.target.value)} placeholder="IT · Engineering" />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className={label}>Environment</label>
          <select className={field} value={environment} onChange={(e) => setEnvironment(e.target.value)}>
            <option value="production">Production</option>
            <option value="staging">Staging</option>
          </select>
        </div>
        <div>
          <label className={label}>Test window <span className="text-ink-faint">(optional)</span></label>
          <input className={field} value={testWindow} onChange={(e) => setTestWindow(e.target.value)} placeholder="Jun 20-25, 09-17" />
        </div>
      </div>
      <div>
        <label className={label}>Rules of engagement</label>
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2.5 rounded-input border border-rule bg-panel px-3.5 py-2.5 text-[13px] text-ink">
            <input type="checkbox" checked={authed} onChange={(e) => setAuthed(e.target.checked)} className="h-4 w-4 accent-[var(--color-accent)]" />
            Authenticated test (provide test credentials)
          </label>
          {authed && <input className={field} value={creds} onChange={(e) => setCreds(e.target.value)} placeholder="test-user / test-pass (or how to obtain)" />}
          <label className="flex items-center gap-2.5 rounded-input border border-rule bg-panel px-3.5 py-2.5 text-[13px] text-ink">
            <input type="checkbox" checked={dos} onChange={(e) => setDos(e.target.checked)} className="h-4 w-4 accent-[var(--color-accent)]" />
            Allow high-intensity / DoS-adjacent checks
          </label>
        </div>
      </div>
      <label className="flex cursor-pointer items-start gap-3 rounded-input border border-accent-soft bg-accent-soft/40 p-3.5">
        <input type="checkbox" checked={attest} onChange={(e) => setAttest(e.target.checked)} className="mt-0.5 h-4 w-4 flex-none accent-[var(--color-accent)]" />
        <span className="text-[12.5px] leading-relaxed text-ink-muted">
          I confirm I <b className="text-ink">own or am authorized</b> to test these assets. (Legally required. The lead verifies this.)
        </span>
      </label>
      <Button type="submit" size="lg" className="w-full" disabled={!attest || busy}>{submitLabel} <ArrowRight size={16} /></Button>
    </form>
  )
}
