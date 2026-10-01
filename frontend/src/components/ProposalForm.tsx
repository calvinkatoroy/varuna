import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

const field = 'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const label = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'

export type ProposalPayload = {
  target: string; in_scope: string; out_of_scope: string; purpose: string; division: string
  environment: string; test_window: string; roe: { authenticated: boolean; credentials: string; dos_allowed: boolean }
  authorization_attested: true; mode: 'standard' | 'advanced'; scan_mode: 'local' | 'cloud'
}

// Does this look like an address only the client's own network can reach? (Cloud scans cannot.)
const looksPrivate = (t: string) => {
  const h = t.trim().replace(/^[a-z]+:\/\//i, '').split(/[/:?#]/)[0].toLowerCase()
  return !!h && (h === 'localhost' || !h.includes('.') || /\.(local|localhost|internal|lan|home|corp|intranet|test)$/.test(h) ||
    /^(127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(h))
}

// The scan-proposal scoping form, shared by the onboarding gate and the in-app "New Proposal".
// Simple/Advanced only changes which fields the submitter is asked - both still go through the
// exact same lead-pentester approval queue (see TeamBoard's Pending column); `mode` just tells
// the team how much scoping detail the client actually gave, same field the review pipeline
// already uses elsewhere (engagements/cards are tagged standard/advanced).
export function ProposalForm({ onSubmit, submitLabel = 'Submit for approval' }: { onSubmit: (p: ProposalPayload) => Promise<void> | void; submitLabel?: string }) {
  const [mode, setMode] = useState<'standard' | 'advanced'>('standard')
  const [scan, setScan] = useState<'local' | 'cloud'>('cloud')
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
    if (!attest || (scan === 'cloud' && looksPrivate(target))) return
    setBusy(true)
    try {
      await onSubmit({
        target, in_scope: target, out_of_scope: outScope, purpose, division, environment,
        test_window: testWindow, roe: { authenticated: authed, credentials: creds, dos_allowed: dos },
        authorization_attested: true, mode, scan_mode: scan,
      })
    } catch {
      // api.ts already surfaced a toast with the real reason - this just makes sure the button
      // un-sticks instead of staying disabled forever on a failed submit.
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="flex gap-1 rounded-pill bg-panel p-1">
        {(['standard', 'advanced'] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`min-h-[44px] flex-1 rounded-pill py-2 text-[13.5px] font-semibold transition-colors ${
              mode === m ? 'bg-card text-ink shadow-sm' : 'text-ink-muted'
            }`}
          >
            {m === 'standard' ? 'Simple' : 'Advanced'}
          </button>
        ))}
      </div>
      <p className="-mt-2 text-[12px] text-ink-muted">
        {mode === 'standard'
          ? 'Just the essentials - your lead pentester fills in the rest during scoping.'
          : 'Full scoping detail, for teams that already know their environment and rules of engagement.'}
      </p>

      <fieldset>
        <legend className={label}>Where should the scan run?</legend>
        <div role="radiogroup" className="grid gap-2 sm:grid-cols-2">
          {([
            ['cloud', 'By Varuna (cloud)', 'Nothing to install. Only for websites that are open on the internet.'],
            ['local', 'On my computer', 'You install a small program once. Needed for internal or private systems.'],
          ] as const).map(([v, title, text]) => (
            <label key={v} className={`flex min-h-[44px] cursor-pointer items-start gap-3 rounded-input border p-3 transition-colors ${scan === v ? 'border-accent bg-accent-soft/40' : 'border-rule bg-panel'}`}>
              <input type="radio" name="scan-mode" value={v} checked={scan === v} onChange={() => setScan(v)} className="mt-1 h-4 w-4 flex-none accent-[var(--color-accent)]" />
              <span><b className="block text-[13px] text-ink">{title}</b><span className="text-[12px] leading-snug text-ink-muted">{text}</span></span>
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label htmlFor="proposal-1" className={label}>In-scope target(s)</label>
        <input id="proposal-1" className={field} value={target} onChange={(e) => setTarget(e.target.value)} placeholder="https://api.acme.io" required />
        {scan === 'cloud' && looksPrivate(target) && (
          <p role="alert" className="mt-2 rounded-input bg-med-bg p-3 text-[12.5px] leading-relaxed text-ink">
            This looks like an internal address, which Varuna's cloud cannot reach.{' '}
            <button type="button" onClick={() => setScan('local')} className="font-semibold text-accent-ink underline">Scan on my computer instead</button>
          </p>
        )}
      </div>
      <div className={mode === 'advanced' ? 'grid grid-cols-2 gap-3' : ''}>
        <div>
          <label htmlFor="proposal-2" className={label}>Purpose (keperluan)</label>
          <select id="proposal-2" className={field} value={purpose} onChange={(e) => setPurpose(e.target.value)}>
            <option value="pre-release">Pre-release</option>
            <option value="compliance">Compliance (ISO/PCI)</option>
            <option value="periodic">Periodic</option>
            <option value="incident">Incident-driven</option>
          </select>
        </div>
        <div className={mode === 'advanced' ? '' : 'mt-4'}>
          <label htmlFor="proposal-3" className={label}>Division</label>
          <input id="proposal-3" className={field} value={division} onChange={(e) => setDivision(e.target.value)} placeholder="IT · Engineering" />
        </div>
      </div>

      {mode === 'advanced' && (
        <>
          <div>
            <label htmlFor="proposal-4" className={label}>Out of scope <span className="text-ink-faint">(optional)</span></label>
            <input id="proposal-4" className={field} value={outScope} onChange={(e) => setOutScope(e.target.value)} placeholder="admin.acme.io, /billing" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="proposal-5" className={label}>Environment</label>
              <select id="proposal-5" className={field} value={environment} onChange={(e) => setEnvironment(e.target.value)}>
                <option value="production">Production</option>
                <option value="staging">Staging</option>
              </select>
            </div>
            <div>
              <label htmlFor="proposal-6" className={label}>Test window <span className="text-ink-faint">(optional)</span></label>
              <input id="proposal-6" className={field} value={testWindow} onChange={(e) => setTestWindow(e.target.value)} placeholder="Jun 20-25, 09-17" />
            </div>
          </div>
          <div role="group" aria-labelledby="proposal-roe">
            <span id="proposal-roe" className={label}>Rules of engagement</span>
            <div className="flex flex-col gap-2">
              <label className="flex min-h-[44px] items-center gap-3 rounded-input border border-rule bg-panel px-3.5 py-2.5 text-[13px] text-ink">
                <input type="checkbox" checked={authed} onChange={(e) => setAuthed(e.target.checked)} className="h-5 w-5 flex-none accent-[var(--color-accent)]" />
                Authenticated test (provide test credentials)
              </label>
              {authed && <input className={field} value={creds} onChange={(e) => setCreds(e.target.value)} aria-label="Test credentials, or how to obtain them" placeholder="test-user / test-pass (or how to obtain)" />}
              <label className="flex min-h-[44px] items-center gap-3 rounded-input border border-rule bg-panel px-3.5 py-2.5 text-[13px] text-ink">
                <input type="checkbox" checked={dos} onChange={(e) => setDos(e.target.checked)} className="h-5 w-5 flex-none accent-[var(--color-accent)]" />
                Allow high-intensity / DoS-adjacent checks
              </label>
            </div>
          </div>
        </>
      )}

      <label className="flex cursor-pointer items-start gap-3 rounded-input border border-accent-soft bg-accent-soft/40 p-3.5">
        <input type="checkbox" checked={attest} onChange={(e) => setAttest(e.target.checked)} className="mt-0.5 h-5 w-5 flex-none accent-[var(--color-accent)]" />
        <span className="text-[12.5px] leading-relaxed text-ink-muted">
          I confirm I <b className="text-ink">own or am authorized</b> to test these assets. (Legally required. The lead verifies this.)
        </span>
      </label>
      <Button type="submit" size="lg" className="w-full" disabled={!attest || busy || (scan === 'cloud' && looksPrivate(target))}>{submitLabel} <ArrowRight size={16} /></Button>
    </form>
  )
}
