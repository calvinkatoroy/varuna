// Mock API router: maps "METHOD /path" to a fixture so the whole app runs with no backend
// (VITE_MOCK=1). Adds small latency for realism. api.ts routes through here when mock is on.
//
// board/findings/proposals are held as mutable module-level state (not read straight off `fx`)
// so that actions taken through the UI (approve, reject, suspend, mark fixed, submit a new
// proposal) actually persist for the session instead of reverting the moment a screen remounts
// and refetches - a real gap the static-fixture-only version had.
import * as fx from './fixtures'

let boardState = structuredClone(fx.board)
let findingsState = structuredClone(fx.findings)
let proposalsState = structuredClone(fx.proposals)

// Accounts are provisioned by an administrator (no self-registration).
// Any password is accepted here, same as the client login - this is a mock, not real auth.
type MockUser = { username: string; name: string; role: string; org_id?: string | null; must_change_password?: boolean }
const teamAccounts: Record<string, MockUser> = {
  admin: { username: 'admin', name: 'Admin', role: 'lead_pentester' },
  riyan: { username: 'riyan', name: 'Riyan', role: 'lead_pentester' },
  dimas: { username: 'dimas', name: 'Dimas', role: 'pentester' },
  aisah: { username: 'aisah', name: 'Aisah', role: 'lead_cyber' },
  hani: { username: 'hani', name: 'Hani', role: 'governance' },
  bayu: { username: 'bayu', name: 'Bayu', role: 'manager' },
  sysadmin: { username: 'sysadmin', name: 'Sysadmin', role: 'sysadmin' },
}
let currentUser: MockUser = fx.me

// System administrator console state (orgs + every account), Indonesian sample data.
let orgsState = structuredClone(fx.orgs)
let accountsState = structuredClone(fx.accounts)
const profiles: Record<string, { display_name: string | null; email: string | null; phone: string | null }> = {}
const tempPassword = () => Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 8)
const fail = (status: number, message: string) => Object.assign(new Error(message), { status })
const orgName = (id?: string | null) => orgsState.find((o) => o.id === id)?.name ?? null

function sysadminRoute(m: string, path: string, body: any): any {
  if (m === 'GET' && path === '/api/sysadmin/orgs') return orgsState
  if (m === 'POST' && path === '/api/sysadmin/orgs') {
    const name = String(body?.name ?? '').trim()
    if (name.length < 2) throw fail(422, 'organization name must be 2-120 characters')
    if (orgsState.some((o) => o.name.toLowerCase() === name.toLowerCase())) throw fail(409, 'an organization with that name already exists')
    const org = { id: 'org-' + Math.random().toString(36).slice(2, 8), name, status: 'active', created_at: '2026-10-08 09:00:00' }
    orgsState = [...orgsState, org].sort((a, b) => a.name.localeCompare(b.name))
    return { id: org.id, name }
  }
  const orgAct = path.match(/^\/api\/sysadmin\/orgs\/([^/]+)\/(enable|disable)$/)
  if (m === 'POST' && orgAct) {
    orgsState = orgsState.map((o) => (o.id === decodeURIComponent(orgAct[1]) ? { ...o, status: orgAct[2] === 'enable' ? 'active' : 'disabled' } : o))
    return { ok: true }
  }
  if (m === 'GET' && path === '/api/sysadmin/accounts') return accountsState
  if (m === 'POST' && path === '/api/sysadmin/accounts') {
    const username = String(body?.username ?? '')
    if (!/^[A-Za-z0-9._-]{3,32}$/.test(username)) throw fail(422, 'username must be 3-32 letters, digits, dot, dash or underscore')
    if ((body.role === 'client') !== !!body.org_id) throw fail(422, 'clients need an organization; staff must not have one')
    if (accountsState.some((a) => a.username.toLowerCase() === username.toLowerCase())) throw fail(409, 'username already taken')
    accountsState = [...accountsState, {
      username, role: body.role, org_id: body.org_id ?? null, display_name: body.display_name ?? null, email: body.email ?? null,
      disabled: 0, totp_enabled: 0, must_change_password: 1, created_at: '2026-10-08 09:00:00',
    }]
    return { username, role: body.role, temp_password: tempPassword() }
  }
  const a = path.match(/^\/api\/sysadmin\/accounts\/([^/]+)\/([a-z-]+)$/)
  if (a) {
    const u = decodeURIComponent(a[1])
    const patch = (p: Record<string, any>) => { accountsState = accountsState.map((x) => (x.username === u ? { ...x, ...p } : x)) }
    if (u === currentUser.username && (a[2] === 'disable' || a[2] === 'role')) throw fail(409, a[2] === 'role' ? 'you cannot change your own role' : 'you cannot disable your own account')
    if (m === 'POST' && a[2] === 'reset-password') { patch({ must_change_password: 1 }); return { temp_password: tempPassword() } }
    if (m === 'POST' && a[2] === 'reset-mfa') { patch({ totp_enabled: 0 }); return { ok: true } }
    if (m === 'POST' && (a[2] === 'enable' || a[2] === 'disable')) { patch({ disabled: a[2] === 'disable' ? 1 : 0 }); return { ok: true } }
    if (m === 'PUT' && a[2] === 'role') { patch({ role: body.role }); return { ok: true } }
    if (m === 'PUT' && a[2] === 'email') { patch({ email: body.email || null }); return { ok: true } }
  }
  return undefined
}

function profileRoute(m: string, path: string, body: any): any {
  const p = (profiles[currentUser.username] ??= {
    display_name: currentUser.name,
    email: currentUser.role === 'client' ? 'it@samudera.co.id' : `${currentUser.username}@varuna.co.id`,
    phone: null,
  })
  if (m === 'GET' && path === '/api/profile') {
    return { username: currentUser.username, role: currentUser.role, org_name: orgName(currentUser.org_id), ...p, totp_enabled: false }
  }
  if (m === 'PUT' && path === '/api/profile') {
    if (body?.display_name != null) p.display_name = body.display_name
    if (body?.phone != null) p.phone = body.phone
    return { ok: true }
  }
  if (m === 'POST' && path === '/api/profile/email') return { ok: true, emailed: true }
  if (m === 'POST' && path === '/api/profile/email/confirm') {
    if (!body?.token || body.token === 'expired') throw fail(422, 'this confirmation link is invalid or has expired')
    return { ok: true }
  }
  return undefined
}

const staticRoutes: Record<string, any> = {
  'GET /api/cockpit': fx.cockpit,
  'GET /api/reports': fx.reports,
  'GET /api/agent': { registered: true, online: true },
}

const purposeLabel: Record<string, string> = {
  'pre-release': 'Pre-release', compliance: 'Compliance', periodic: 'Periodic', incident: 'Incident',
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function isMock(): boolean {
  return String((import.meta as any).env?.VITE_MOCK ?? '1') === '1'
}

export async function mockRequest(method: string, path: string, body?: any): Promise<any> {
  await delay(160)
  const m = method.toUpperCase()

  if (m === 'GET' && path === '/api/me') return { must_change_password: false, org_id: null, ...currentUser }
  if (m === 'POST' && path === '/api/login') {
    const acct = teamAccounts[String(body?.username ?? '').toLowerCase()]
    currentUser = acct ?? fx.me
    return { token: 'mock.jwt.' + currentUser.role }
  }
  if (m === 'POST' && path === '/api/password') return { ok: true, token: 'mock.jwt.' + currentUser.role }
  if (m === 'POST' && path === '/api/refresh') return { token: 'mock.jwt.' + currentUser.role }
  if (m === 'GET' && path === '/api/mfa') return { enabled: false, required: false }
  if (m === 'POST' && path === '/api/mfa/setup') return { secret: 'JBSWY3DPEHPK3PXP', uri: `otpauth://totp/Varuna:${currentUser.username}?secret=JBSWY3DPEHPK3PXP&issuer=Varuna` }
  if (m === 'POST' && (path === '/api/mfa/enable' || path === '/api/mfa/disable')) return { enabled: path.endsWith('enable'), token: 'mock.jwt.' + currentUser.role }
  if (path.startsWith('/api/sysadmin/')) {
    const r = sysadminRoute(m, path, body)
    if (r !== undefined) return r
  }
  if (path.startsWith('/api/profile')) {
    const r = profileRoute(m, path, body)
    if (r !== undefined) return r
  }
  if (m === 'POST' && path.startsWith('/api/password-reset/')) return { ok: true }
  if (m === 'GET' && path === '/api/templates') return ['Full Technical', 'Formal Handover', 'Executive Summary', 'Raw Findings']
  if (m === 'GET' && path === '/api/proposals') return proposalsState
  if (m === 'GET' && path === '/api/findings') return findingsState
  if (m === 'GET' && path === '/api/pipeline/board') return boardState
  const detailMatch = m === 'GET' && path.match(/^\/api\/pipeline\/detail\/(.+)$/)
  if (detailMatch) return (fx.engagementDetail as any)[detailMatch[1]] ?? null

  if (m === 'POST' && path === '/api/proposals') {
    proposalsState = [
      { id: 'pr-' + Math.random().toString(36).slice(2, 7), target: body.target, purpose: purposeLabel[body.purpose] ?? body.purpose, division: body.division, status: 'pending', when: 'Just now' },
      ...proposalsState,
    ]
    return { ok: true }
  }
  if (m === 'POST' && path === '/api/pipeline/move') {
    const { id, from, to } = body
    const card = boardState.find((c) => c.id === from)?.cards.find((k) => k.id === id)
    if (card) boardState = boardState.map((c) => (c.id === from ? { ...c, cards: c.cards.filter((k) => k.id !== id) } : c.id === to ? { ...c, cards: [card, ...c.cards] } : c))
    return { ok: true }
  }
  if (m === 'POST' && path === '/api/pipeline/reject') {
    const { id, from, reason } = body
    const card = boardState.find((c) => c.id === from)?.cards.find((k) => k.id === id)
    if (card) {
      const rejected = { ...card, rejectReason: reason || 'No reason recorded.' }
      boardState = boardState.map((c) => (c.id === from ? { ...c, cards: c.cards.filter((k) => k.id !== id) } : c.id === 'rejected' ? { ...c, cards: [rejected, ...c.cards] } : c))
    }
    return { ok: true }
  }
  if (m === 'POST' && path === '/api/pipeline/suspend') {
    const { id, col, suspended } = body
    boardState = boardState.map((c) => (c.id === col ? { ...c, cards: c.cards.map((k) => (k.id === id ? { ...k, suspended } : k)) } : c))
    return { ok: true }
  }
  if (m === 'POST' && path === '/api/findings/verdict') {
    const { id, verdict } = body
    findingsState = findingsState.map((f) => (f.id === id ? { ...f, verdict } : f))
    return { ok: true }
  }
  if (m === 'POST' && path === '/api/findings/status') {
    const { id, status } = body
    findingsState = findingsState.map((f) => (f.id === id ? { ...f, status } : f))
    return { ok: true }
  }

  const key = `${m} ${path}`
  if (key in staticRoutes) return staticRoutes[key]
  // Remaining POST actions succeed optimistically in the prototype.
  if (m === 'POST') return { ok: true, id: 'mock-' + Math.random().toString(36).slice(2, 8) }
  return {}
}
