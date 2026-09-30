import { useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound, UserPlus, Power } from 'lucide-react'
import { api } from '@/api'
import { toast } from '@/lib/toast'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/BrandMark'
import { TeamAccount } from '@/components/TeamAccount'
import { ErrorRetry } from '@/components/ErrorRetry'
import { useApiData } from '@/lib/useApiData'

type Acct = { username: string; role: string; disabled: number; created_at: string }
const ROLES = ['pentester', 'lead_pentester', 'reporter', 'governance', 'soc', 'client']
const field = 'rounded-input border border-rule bg-panel px-3 py-2.5 text-[13px] text-ink outline-none focus:border-accent'

// Lead-pentester screen: provision team accounts, reset a forgotten password, disable a leaver.
// Everything here is the private-plane admin API (lead only, audited server-side).
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

  return (
    <div className="mx-auto max-w-[1000px] p-[clamp(10px,2vw,28px)]">
      <header className="mb-5 flex flex-wrap items-center gap-4 rounded-bento-lg bg-card px-6 py-4">
        <Link to="/team" className="flex items-center gap-2.5 text-[18px] font-bold tracking-[-0.02em] text-ink"><BrandMark size={28} /> Varuna</Link>
        <h1 className="text-[18px] font-bold text-ink">Team accounts</h1>
        <div className="ml-auto flex items-center gap-3">
          <Link to="/team" className="text-[13px] font-semibold text-accent">Back to board</Link>
          <TeamAccount />
        </div>
      </header>

      <form onSubmit={create} className="mb-5 flex flex-wrap items-end gap-3 rounded-bento bg-card p-5">
        <div><label className="mb-1 block text-[12px] text-ink-muted">Username</label><input className={field} value={n.username} onChange={(e) => setN({ ...n, username: e.target.value })} required minLength={3} /></div>
        <div><label className="mb-1 block text-[12px] text-ink-muted">Password (8+)</label><input className={field} type="password" autoComplete="new-password" value={n.password} onChange={(e) => setN({ ...n, password: e.target.value })} required minLength={8} /></div>
        <div><label className="mb-1 block text-[12px] text-ink-muted">Role</label><select className={field} value={n.role} onChange={(e) => setN({ ...n, role: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select></div>
        <Button type="submit"><UserPlus size={15} /> Create</Button>
      </form>

      {error ? <ErrorRetry message={error} onRetry={reload} /> : (
        <div className="overflow-x-auto rounded-bento bg-card">
          <table className="w-full text-left text-[13px]">
            <thead><tr className="border-b border-rule text-[11.5px] uppercase tracking-wide text-ink-faint"><th className="px-5 py-3">User</th><th>Role</th><th>Status</th><th className="pr-5 text-right">Actions</th></tr></thead>
            <tbody>
              {(data ?? []).map((a) => (
                <tr key={a.username} className="border-b border-rule/60 last:border-0">
                  <td className="max-w-[260px] truncate px-5 py-3 font-semibold text-ink" title={a.username}>{a.username}</td>
                  <td className="text-ink-muted">{a.role}</td>
                  <td>{a.disabled ? <span className="font-semibold text-crit">Disabled</span> : <span className="text-low">Active</span>}</td>
                  <td className="pr-5 text-right">
                    <button onClick={() => reset(a.username)} className="mr-3 inline-flex items-center gap-1 font-semibold text-accent"><KeyRound size={13} /> Reset password</button>
                    <button onClick={() => run(api.ppost(`/api/admin/accounts/${a.username}/${a.disabled ? 'enable' : 'disable'}`), `${a.username} ${a.disabled ? 'enabled' : 'disabled'}.`)} className="inline-flex items-center gap-1 font-semibold text-ink-muted"><Power size={13} /> {a.disabled ? 'Enable' : 'Disable'}</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
