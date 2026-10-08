import { useEffect, useMemo, useState } from 'react'
import * as Tabs from '@radix-ui/react-tabs'
import * as Dialog from '@radix-ui/react-dialog'
import { Building2, Check, Copy, KeyRound, Mail, Power, ShieldCheck, ShieldOff, UserPlus, Users } from 'lucide-react'
import { sysadmin, type Account, type Org } from '@/api'
import { useAuth } from '@/auth'
import { toast } from '@/lib/toast'
import { useApiData } from '@/lib/useApiData'
import { ROLE_LABEL, STAFF_ROLES, roleLabel, type Role } from '@/lib/roles'
import { Button } from '@/components/ui/button'
import { BrandMark } from '@/components/BrandMark'
import { TeamAccount } from '@/components/TeamAccount'
import { ErrorRetry } from '@/components/ErrorRetry'

const field = 'min-h-[44px] w-full rounded-input border border-rule bg-panel px-3 py-2.5 text-[14px] text-ink outline-none focus:border-accent'
const lbl = 'mb-1 block text-[12.5px] text-ink-muted'
const act = 'inline-flex min-h-[44px] items-center gap-1.5 rounded-md px-2 text-[13px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus'
const tab = 'inline-flex min-h-[44px] items-center gap-2 rounded-pill px-4 text-[13.5px] font-semibold text-ink-muted transition-colors hover:text-ink data-[state=active]:bg-card data-[state=active]:text-ink data-[state=active]:shadow-[0_4px_14px_rgba(0,0,0,.16)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus'
const ALL_ROLES = Object.keys(ROLE_LABEL) as Role[]
const yes = (v: unknown) => !!v

// Status always says it in words; colour only backs it up.
function Chip({ ok, on, off }: { ok: boolean; on: string; off: string }) {
  return (
    <span className={`inline-flex items-center rounded-pill px-2.5 py-0.5 text-[12px] font-semibold ${ok ? 'bg-low-bg text-low' : 'bg-crit-bg text-crit'}`}>
      {ok ? on : off}
    </span>
  )
}

// Two-step confirm, same as the review board: the first tap arms and says what will happen, the second
// commits. Disarms after 8 seconds.
function useTwoStep() {
  const [armed, setArmed] = useState<string | null>(null)
  useEffect(() => {
    if (!armed) return
    const t = setTimeout(() => setArmed(null), 8000)
    return () => clearTimeout(t)
  }, [armed])
  const twoStep = (key: string, run: () => void) => { if (armed === key) { setArmed(null); run() } else setArmed(key) }
  return { armed, twoStep }
}

// The temporary password exists only in this response: shown once, with a copy button, never again.
function TempPasswordDialog({ shown, onClose }: { shown: { username: string; password: string; created: boolean } | null; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  useEffect(() => setCopied(false), [shown])
  const copy = async () => {
    try { await navigator.clipboard.writeText(shown!.password); setCopied(true) } catch { toast('Copy failed. Select the password and copy it by hand.') }
  }
  return (
    <Dialog.Root open={!!shown} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[60] bg-shell/60" />
        <Dialog.Content
          onInteractOutside={(e) => e.preventDefault()}
          className="fixed left-1/2 top-1/2 z-[61] w-[calc(100%-32px)] max-w-[440px] -translate-x-1/2 -translate-y-1/2 space-y-4 rounded-bento-lg border border-rule bg-card p-7 shadow-[0_30px_80px_-20px_rgba(0,0,0,.6)] focus:outline-none"
        >
          <Dialog.Title className="text-[18px] font-bold tracking-[-0.02em] text-ink">
            {shown?.created ? `Account ${shown.username} created` : `New password for ${shown?.username}`}
          </Dialog.Title>
          <Dialog.Description className="text-[13px] leading-relaxed text-ink-muted">
            Temporary password. Give it to the person over a separate channel (phone or in person, not in the same email as the username). They must choose their own password the first time they sign in.
          </Dialog.Description>
          <div className="flex items-center gap-2 rounded-input border border-rule bg-panel px-3 py-1.5">
            <code className="min-w-0 flex-1 select-all break-all font-mono text-[15px] tracking-wider text-ink" data-testid="temp-password">{shown?.password}</code>
            <button type="button" onClick={copy} aria-label="Copy temporary password" className="grid h-11 w-11 flex-none place-items-center rounded-full text-ink-muted hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus">
              {copied ? <Check size={17} className="text-low" /> : <Copy size={17} />}
            </button>
          </div>
          <p role="status" className="rounded-input bg-med-bg p-3 text-[12.5px] font-semibold leading-relaxed text-ink">
            {copied ? 'Copied. ' : ''}Shown only once. After you close this, nobody can see it again; reset the password to issue a new one.
          </p>
          <Dialog.Close asChild><Button className="w-full">I have copied it</Button></Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function Organizations({ orgs, accounts, reload }: { orgs: Org[] | null; accounts: Account[]; reload: () => void }) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const { armed, twoStep } = useTwoStep()
  const members = (id: string) => accounts.filter((a) => a.org_id === id).length

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const o = await sysadmin.createOrg(name.trim())
      toast(`Created ${o.name}.`)
      setName('')
      reload()
    } catch {} finally { setBusy(false) }
  }
  const toggle = (o: Org) => {
    const enable = o.status !== 'active'
    sysadmin.setOrg(o.id, enable).then(() => { toast(`${o.name} ${enable ? 'enabled' : 'disabled'}.`); reload() }).catch(() => {})
  }

  return (
    <>
      <form onSubmit={create} className="mb-4 grid gap-3 rounded-bento bg-card p-5 sm:grid-cols-[1fr_auto] sm:items-end">
        <div>
          <label htmlFor="org-name" className={lbl}>New organization name</label>
          <input id="org-name" className={field} value={name} onChange={(e) => setName(e.target.value)} placeholder="PT Samudera Logistik" required minLength={2} maxLength={120} autoComplete="off" />
        </div>
        <Button type="submit" disabled={busy}><Building2 size={15} /> Create organization</Button>
      </form>
      {!orgs ? <div className="p-6 text-[13px] text-ink-muted">Loading…</div> : orgs.length === 0 ? (
        <div className="rounded-bento bg-card p-6 text-[13px] text-ink-muted">No organizations yet. Create one above, then add its client accounts.</div>
      ) : (
        <ul className="space-y-2.5">
          {orgs.map((o) => {
            const active = o.status === 'active'
            const key = `org:${o.id}`
            return (
              <li key={o.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-bento bg-card px-5 py-3">
                <div className="min-w-0 flex-1">
                  <div className="break-words text-[15px] font-semibold text-ink">{o.name}</div>
                  <div className="text-[12.5px] text-ink-muted">{members(o.id)} client account{members(o.id) === 1 ? '' : 's'}</div>
                </div>
                <Chip ok={active} on="Active" off="Disabled" />
                <button
                  onClick={() => (active ? twoStep(key, () => toggle(o)) : toggle(o))}
                  className={`${act} ${active ? 'text-crit' : 'text-accent-ink'}`}
                  aria-label={active ? `Disable ${o.name}` : `Enable ${o.name}`}
                >
                  <Power size={14} /> {active ? (armed === key ? 'Tap again: signs out all its users' : 'Disable') : 'Enable'}
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </>
  )
}

type Draft = { username: string; role: Role; org_id: string; display_name: string; email: string }
const EMPTY: Draft = { username: '', role: 'client', org_id: '', display_name: '', email: '' }

function Accounts({ orgs, accounts, reload, onTemp }: {
  orgs: Org[]; accounts: Account[] | null; reload: () => void
  onTemp: (t: { username: string; password: string; created: boolean }) => void
}) {
  const { user } = useAuth()
  const [d, setD] = useState<Draft>(EMPTY)
  const [busy, setBusy] = useState(false)
  const { armed, twoStep } = useTwoStep()
  const orgName = useMemo(() => Object.fromEntries(orgs.map((o) => [o.id, o.name])), [orgs])
  const activeOrgs = orgs.filter((o) => o.status === 'active')
  const isClientDraft = d.role === 'client'

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      const r = await sysadmin.createAccount({
        username: d.username.trim(), role: d.role,
        ...(isClientDraft ? { org_id: d.org_id } : {}),
        ...(d.display_name.trim() ? { display_name: d.display_name.trim() } : {}),
        ...(d.email.trim() ? { email: d.email.trim() } : {}),
      })
      onTemp({ username: r.username, password: r.temp_password, created: true })
      setD({ ...EMPTY, role: d.role, org_id: d.org_id })
      reload()
    } catch {} finally { setBusy(false) }
  }
  const run = (p: Promise<unknown>, msg: string) => p.then(() => { toast(msg); reload() }).catch(() => {})
  const resetPw = (a: Account) => sysadmin.resetPassword(a.username).then((r) => { onTemp({ username: a.username, password: r.temp_password, created: false }); reload() }).catch(() => {})
  const resetMfa = (a: Account) => run(sysadmin.resetMfa(a.username), `Two-factor reset for ${a.username}. They set it up again at next sign-in.`)
  const toggle = (a: Account) => run(sysadmin.setDisabled(a.username, !yes(a.disabled)), `${a.username} ${a.disabled ? 'enabled' : 'disabled'}.`)
  const setEmail = (a: Account) => {
    const v = window.prompt(`Email for ${a.username} (leave empty to clear)`, a.email ?? '')
    if (v !== null) run(sysadmin.setEmail(a.username, v.trim()), v.trim() ? `Email set for ${a.username}.` : `Email cleared for ${a.username}.`)
  }
  const setRole = (a: Account, role: string) => run(sysadmin.setRole(a.username, role), `${a.username} is now ${roleLabel(role)}.`)

  const status = (a: Account) => (
    <div className="flex flex-wrap items-center gap-1.5">
      <Chip ok={!yes(a.disabled)} on="Active" off="Disabled" />
      {yes(a.must_change_password) && <span className="inline-flex items-center rounded-pill bg-med-bg px-2.5 py-0.5 text-[12px] font-semibold text-ink">Temporary password</span>}
    </div>
  )
  const twofa = (a: Account) => (yes(a.totp_enabled)
    ? <span className="inline-flex items-center gap-1 text-[12.5px] text-ink"><ShieldCheck size={13} className="text-low" /> 2FA on</span>
    : <span className="inline-flex items-center gap-1 text-[12.5px] text-ink-muted"><ShieldOff size={13} /> 2FA off</span>)
  const actions = (a: Account) => {
    const self = a.username === user?.username
    const k = (s: string) => `${s}:${a.username}`
    return (
      <>
        <button onClick={() => twoStep(k('pw'), () => resetPw(a))} className={`${act} text-accent-ink`}>
          <KeyRound size={14} /> {armed === k('pw') ? 'Tap again to reset' : 'Reset password'}
        </button>
        <button onClick={() => setEmail(a)} className={`${act} text-accent-ink`}>
          <Mail size={14} /> Set email
        </button>
        {yes(a.totp_enabled) && (
          <button onClick={() => twoStep(k('mfa'), () => resetMfa(a))} className={`${act} text-accent-ink`}>
            {armed === k('mfa') ? 'Tap again to reset 2FA' : 'Reset 2FA'}
          </button>
        )}
        {!self && (
          <button
            onClick={() => (yes(a.disabled) ? toggle(a) : twoStep(k('off'), () => toggle(a)))}
            className={`${act} ${yes(a.disabled) ? 'text-accent-ink' : 'text-crit'}`}
          >
            <Power size={14} /> {yes(a.disabled) ? 'Enable' : armed === k('off') ? 'Tap again to disable' : 'Disable'}
          </button>
        )}
      </>
    )
  }
  // Staff roles can be switched (never your own, never to or from client).
  const roleCell = (a: Account) => {
    if (a.role === 'client' || a.username === user?.username) return <span className="text-ink-muted">{roleLabel(a.role)}</span>
    return (
      <select aria-label={`Role for ${a.username}`} className={`${field} w-auto min-w-[170px] py-1.5`} value={a.role} onChange={(e) => setRole(a, e.target.value)}>
        {STAFF_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
      </select>
    )
  }
  const orgCell = (a: Account) => (a.org_id ? orgName[a.org_id] ?? a.org_id : <span className="text-ink-muted">Staff</span>)

  return (
    <>
      <form onSubmit={create} className="mb-4 rounded-bento bg-card p-5" aria-labelledby="new-acct-title">
        <h2 id="new-acct-title" className="mb-3 text-[15px] font-bold text-ink">New account</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label htmlFor="acct-role" className={lbl}>Role</label>
            <select id="acct-role" className={field} value={d.role} onChange={(e) => setD({ ...d, role: e.target.value as Role })}>
              {ALL_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </select>
          </div>
          {isClientDraft && (
            <div>
              <label htmlFor="acct-org" className={lbl}>Organization (required for clients)</label>
              <select id="acct-org" className={field} value={d.org_id} onChange={(e) => setD({ ...d, org_id: e.target.value })} required>
                <option value="">Choose an organization</option>
                {activeOrgs.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
              </select>
              {activeOrgs.length === 0 && <p className="mt-1 text-[12px] text-ink-muted">Create an active organization first.</p>}
            </div>
          )}
          <div>
            <label htmlFor="acct-user" className={lbl}>Username (3-32: letters, digits, . _ -)</label>
            <input id="acct-user" className={field} value={d.username} onChange={(e) => setD({ ...d, username: e.target.value })} required minLength={3} maxLength={32} pattern="[A-Za-z0-9._\-]{3,32}" autoCapitalize="none" autoCorrect="off" spellCheck={false} autoComplete="off" placeholder="budi.santoso" />
          </div>
          <div>
            <label htmlFor="acct-name" className={lbl}>Display name (optional)</label>
            <input id="acct-name" className={field} value={d.display_name} onChange={(e) => setD({ ...d, display_name: e.target.value })} maxLength={120} autoComplete="off" placeholder="Budi Santoso" />
          </div>
          <div>
            <label htmlFor="acct-email" className={lbl}>Email (optional, for password resets)</label>
            <input id="acct-email" className={field} type="email" value={d.email} onChange={(e) => setD({ ...d, email: e.target.value })} autoComplete="off" placeholder="budi@samudera.co.id" />
          </div>
        </div>
        <p className="mt-3 text-[12.5px] leading-relaxed text-ink-muted">Varuna generates a temporary password and shows it once. The person picks their own at first sign-in.</p>
        <Button type="submit" className="mt-3" disabled={busy || (isClientDraft && !d.org_id)}><UserPlus size={15} /> Create account</Button>
      </form>

      {!accounts ? <div className="p-6 text-[13px] text-ink-muted">Loading…</div> : (
        <>
          {/* phone: one card per person, nothing scrolls sideways */}
          <ul className="space-y-3 md:hidden">
            {accounts.map((a) => (
              <li key={a.username} className="rounded-bento bg-card p-4">
                <div className="min-w-0">
                  <div className="break-words text-[15px] font-semibold text-ink">{a.username}</div>
                  {a.display_name && <div className="break-words text-[13px] text-ink-muted">{a.display_name}</div>}
                </div>
                <dl className="mt-2 grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1.5 text-[13px]">
                  <dt className="text-ink-muted">Role</dt><dd className="text-ink">{roleCell(a)}</dd>
                  <dt className="text-ink-muted">Organization</dt><dd className="break-words text-ink">{orgCell(a)}</dd>
                  <dt className="text-ink-muted">Status</dt><dd>{status(a)}</dd>
                  <dt className="text-ink-muted">Sign-in</dt><dd>{twofa(a)}</dd>
                </dl>
                <div className="mt-2 flex flex-wrap gap-x-1 border-t border-rule pt-2">{actions(a)}</div>
              </li>
            ))}
          </ul>

          {/* tablet and up: a table */}
          <div className="hidden overflow-x-auto rounded-bento bg-card md:block">
            <table className="w-full text-left text-[13px]">
              <thead>
                <tr className="border-b border-rule text-[12px] uppercase tracking-wide text-ink-muted">
                  <th className="px-5 py-3" scope="col">User</th><th scope="col">Role</th><th scope="col">Organization</th>
                  <th scope="col">Status</th><th scope="col">2FA</th><th className="pr-5 text-right" scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((a) => (
                  <tr key={a.username} className="border-b border-rule/60 align-middle last:border-0">
                    <td className="max-w-[220px] px-5 py-2">
                      <div className="truncate font-semibold text-ink" title={a.username}>{a.username}</div>
                      {a.display_name && <div className="truncate text-[12.5px] text-ink-muted" title={a.display_name}>{a.display_name}</div>}
                    </td>
                    <td className="py-2 pr-3">{roleCell(a)}</td>
                    <td className="max-w-[200px] truncate pr-3 text-ink">{orgCell(a)}</td>
                    <td className="pr-3">{status(a)}</td>
                    <td className="pr-3">{twofa(a)}</td>
                    <td className="pr-5 text-right"><div className="flex flex-wrap justify-end">{actions(a)}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}

// System administrator console: organizations, client users and staff. Provisioning only: a
// sysadmin has no access to tenant data (board, findings, reports), so this is its whole app.
export default function SysAdmin() {
  const orgs = useApiData<Org[]>(() => sysadmin.orgs())
  const accounts = useApiData<Account[]>(() => sysadmin.accounts())
  const [temp, setTemp] = useState<{ username: string; password: string; created: boolean } | null>(null)
  const reload = () => { orgs.reload(); accounts.reload() }
  const error = orgs.error || accounts.error

  return (
    <div className="mx-auto max-w-[1100px] p-[clamp(10px,2vw,28px)]">
      <a href="#main" className="sr-only rounded-pill bg-cta-bg px-4 py-2 text-[13px] font-semibold text-cta-fg focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[70] focus:px-5 focus:py-3 focus:shadow-lg">Skip to content</a>
      <header className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-bento-lg bg-card px-5 py-3.5 sm:px-6">
        <span className="flex items-center gap-2.5 text-[18px] font-bold tracking-[-0.02em] text-ink"><BrandMark size={28} /> <span className="hidden sm:inline">Varuna</span></span>
        <h1 className="text-[18px] font-bold text-ink">Administration</h1>
        <div className="ml-auto"><TeamAccount /></div>
      </header>

      <main id="main" tabIndex={-1} className="focus:outline-none">
        {error ? <ErrorRetry message={error} onRetry={reload} /> : (
          <Tabs.Root defaultValue="orgs">
            <Tabs.List aria-label="Administration" className="mb-4 inline-flex gap-1 rounded-pill bg-panel p-1">
              <Tabs.Trigger value="orgs" className={tab}><Building2 size={15} /> Organizations</Tabs.Trigger>
              <Tabs.Trigger value="accounts" className={tab}><Users size={15} /> Accounts</Tabs.Trigger>
            </Tabs.List>
            <Tabs.Content value="orgs" className="focus:outline-none">
              <Organizations orgs={orgs.data} accounts={accounts.data ?? []} reload={reload} />
            </Tabs.Content>
            <Tabs.Content value="accounts" className="focus:outline-none">
              <Accounts orgs={orgs.data ?? []} accounts={accounts.data} reload={reload} onTemp={setTemp} />
            </Tabs.Content>
          </Tabs.Root>
        )}
      </main>
      <TempPasswordDialog shown={temp} onClose={() => setTemp(null)} />
    </div>
  )
}
