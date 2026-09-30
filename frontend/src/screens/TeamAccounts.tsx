import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, KeyRound, ShieldCheck, UserPlus, Power } from 'lucide-react'
import { api } from '@/api'
import { toast } from '@/lib/toast'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/BrandMark'
import { TeamAccount } from '@/components/TeamAccount'
import { ErrorRetry } from '@/components/ErrorRetry'
import { useApiData } from '@/lib/useApiData'

type Acct = { username: string; role: string; disabled: number; totp_enabled: number; created_at: string }
const ROLES = ['pentester', 'lead_pentester', 'reporter', 'governance', 'soc', 'client']
const roleName = (r: string) => r.replace('_', ' ')
const field = 'min-h-[44px] w-full rounded-input border border-rule bg-panel px-3 py-2.5 text-[14px] text-ink outline-none focus:border-accent'
const act = 'inline-flex min-h-[44px] items-center gap-1.5 rounded-md px-2 text-[13px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus'

// Lead-pentester screen: provision team accounts, reset a forgotten password or lost phone,
// disable a leaver. Everything here is the private-plane admin API (lead only, audited).
// Wide screens get a table; on a phone each person is a card, so nothing needs sideways scrolling.
export default function TeamAccounts() {
  const { data, error, reload } = useApiData<Acct[]>(() => api.pget('/api/admin/accounts'))
  const [n, setN] = useState({ username: '', password: '', role: 'pentester' })

  const run = (p: Promise<unknown>, msg: string) => p.then(() => { toast(msg); reload() }).catch(() => {})
  const create = (e: React.FormEvent) => {
    e.preventDefault()
    run(api.ppost('/api/admin/accounts', n), `Created ${n.username}.`).then(() => setN({ username: '', password: '', role: n.role }))
  }
  const reset = (u: string) => {
    const pw = window.prompt(`New password for ${u} (8+ characters):`)
    if (pw) run(api.ppost(`/api/admin/accounts/${u}/reset-password`, { password: pw }), `Password reset for ${u}.`)
  }
  const toggle = (a: Acct) => run(api.ppost(`/api/admin/accounts/${a.username}/${a.disabled ? 'enable' : 'disable'}`), `${a.username} ${a.disabled ? 'enabled' : 'disabled'}.`)
  const reset2fa = (a: Acct) => run(api.ppost(`/api/admin/accounts/${a.username}/reset-mfa`), `Two-factor reset for ${a.username}.`)

  return (
    <div className="mx-auto max-w-[1000px] p-[clamp(10px,2vw,28px)]">
      <a href="#main" className="sr-only rounded-pill bg-cta-bg px-4 py-2 text-[13px] font-semibold text-cta-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:px-5 focus:py-3 focus:shadow-lg">Skip to content</a>
      <header className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-bento-lg bg-card px-5 py-3.5 sm:px-6">
        <Link to="/team" aria-label="Back to the board" className="-ml-2 grid h-11 w-11 place-items-center rounded-full text-ink-muted hover:text-ink sm:hidden"><ArrowLeft size={20} /></Link>
        <Link to="/team" className="hidden items-center gap-2.5 text-[18px] font-bold tracking-[-0.02em] text-ink sm:flex"><BrandMark size={28} /> Varuna</Link>
        <h1 className="text-[18px] font-bold text-ink">Team accounts</h1>
        <div className="ml-auto flex items-center gap-3">
          <Link to="/team" className="hidden min-h-[44px] items-center text-[13px] font-semibold text-accent-ink sm:inline-flex">Back to board</Link>
          <TeamAccount />
        </div>
      </header>

      <main id="main" tabIndex={-1} className="focus:outline-none">
      <form onSubmit={create} className="mb-5 grid gap-3 rounded-bento bg-card p-5 sm:grid-cols-[1fr_1fr_auto_auto] sm:items-end">
        <label className="block"><span className="mb-1 block text-[12.5px] text-ink-muted">Username</span><input className={field} value={n.username} onChange={(e) => setN({ ...n, username: e.target.value })} required minLength={3} autoComplete="off" /></label>
        <label className="block"><span className="mb-1 block text-[12.5px] text-ink-muted">Password (8 or more characters)</span><input className={field} type="password" autoComplete="new-password" value={n.password} onChange={(e) => setN({ ...n, password: e.target.value })} required minLength={8} /></label>
        <label className="block"><span className="mb-1 block text-[12.5px] text-ink-muted">Role</span><select className={field} value={n.role} onChange={(e) => setN({ ...n, role: e.target.value })}>{ROLES.map((r) => <option key={r} value={r}>{roleName(r)}</option>)}</select></label>
        <Button type="submit" className="min-h-[44px]"><UserPlus size={15} /> Create</Button>
      </form>

      {error ? <ErrorRetry message={error} onRetry={reload} /> : (
        <>
          {/* phone: one card per person */}
          <ul className="space-y-3 md:hidden">
            {(data ?? []).map((a) => (
              <li key={a.username} className="rounded-bento bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="break-words text-[15px] font-semibold text-ink">{a.username}</div>
                    <div className="mt-0.5 text-[12.5px] capitalize text-ink-muted">{roleName(a.role)}</div>
                  </div>
                  <div className="flex flex-none flex-col items-end gap-1 text-[12px]">
                    {a.disabled ? <span className="font-semibold text-crit">Disabled</span> : <span className="text-low">Active</span>}
                    {a.totp_enabled ? <span className="inline-flex items-center gap-1 text-ink-muted"><ShieldCheck size={12} /> Two-factor on</span> : null}
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-1 border-t border-rule pt-2">
                  <button onClick={() => reset(a.username)} className={`${act} text-accent-ink`}><KeyRound size={14} /> Reset password</button>
                  {a.totp_enabled ? <button onClick={() => reset2fa(a)} className={`${act} text-accent-ink`}>Reset 2FA</button> : null}
                  <button onClick={() => toggle(a)} className={`${act} text-ink-muted`}><Power size={14} /> {a.disabled ? 'Enable' : 'Disable'}</button>
                </div>
              </li>
            ))}
          </ul>

          {/* tablet and up: a table */}
          <div className="hidden overflow-x-auto rounded-bento bg-card md:block">
            <table className="w-full text-left text-[13px]">
              <thead><tr className="border-b border-rule text-[12px] uppercase tracking-wide text-ink-faint"><th className="px-5 py-3" scope="col">User</th><th scope="col">Role</th><th scope="col">Status</th><th scope="col">2FA</th><th className="pr-5 text-right" scope="col">Actions</th></tr></thead>
              <tbody>
                {(data ?? []).map((a) => (
                  <tr key={a.username} className="border-b border-rule/60 last:border-0">
                    <td className="max-w-[260px] truncate px-5 py-2 font-semibold text-ink" title={a.username}>{a.username}</td>
                    <td className="capitalize text-ink-muted">{roleName(a.role)}</td>
                    <td>{a.disabled ? <span className="font-semibold text-crit">Disabled</span> : <span className="text-low">Active</span>}</td>
                    <td className="text-ink-muted">{a.totp_enabled ? 'On' : '-'}</td>
                    <td className="pr-5 text-right">
                      <button onClick={() => reset(a.username)} className={`${act} text-accent-ink`}><KeyRound size={13} /> Reset password</button>
                      {a.totp_enabled ? <button onClick={() => reset2fa(a)} className={`${act} text-accent-ink`}>Reset 2FA</button> : null}
                      <button onClick={() => toggle(a)} className={`${act} text-ink-muted`}><Power size={13} /> {a.disabled ? 'Enable' : 'Disable'}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      </main>

    </div>
  )
}
