// API client: JWT bearer + two base URLs (public plane, private/Tailscale plane).
// Public defaults to same-origin ('' -> /api proxied by Vite/Caddy); private defaults to the
// dev port and is set to the Tailscale host in production via VITE_PRIVATE_API.

import { isMock, mockRequest } from './mock'
import { toast } from './lib/toast'

// Fired on any 401 so something outside this module can react (auth.tsx clears the stale
// user/session instead of leaving the app looking logged-in while every request quietly 401s
// forever). A plain window event, not a callback registry - api.ts has no business importing
// the auth context, and this is the one thing worth decoupling that way.
export const UNAUTHORIZED_EVENT = 'varuna:unauthorized'
// Fired on 403 password_change_required: the account carries a temporary password (set by the
// system administrator), so the app must open the forced change dialog before anything else works.
export const PASSWORD_CHANGE_EVENT = 'varuna:password-change-required'
const SESSION_ENDED = 'Your session ended. Please sign in again.'

const PUBLIC = (import.meta as any).env.VITE_PUBLIC_API || ''
// 'same' = the team origin serves the private API itself (Caddy :8080), so no cross-origin call.
const _priv = (import.meta as any).env.VITE_PRIVATE_API
const PRIVATE = _priv === 'same' ? '' : _priv || 'http://localhost:8010'

let token: string | null = localStorage.getItem('varuna_jwt')

export function setToken(t: string | null) {
  token = t
  if (t) localStorage.setItem('varuna_jwt', t)
  else localStorage.removeItem('varuna_jwt')
}
// Another tab logged out, or a different person logged in there: this tab must not keep acting as the
// old user (and must never mix one person's screen with another's token). Reloading re-reads the session.
// A refreshed or re-issued token for the SAME person (background refresh, password or two-factor change in
// another tab) is simply adopted: reloading every tab each time one of them refreshed would lose work.
// The JWT names the person in its `sub` claim.
const tokenUser = (t: string | null) => {
  if (!t) return null
  try { return JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).sub ?? t } catch { return t }
}
window.addEventListener('storage', (e) => {
  if (e.key !== 'varuna_jwt' || e.newValue === token) return
  if (e.newValue && tokenUser(e.newValue) === tokenUser(token)) token = e.newValue
  else location.reload()
})

export function getToken() {
  return token
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public silent = false) {
    super(message)
  }
}

// `quiet`: background calls (token refresh) never toast their own failures; a 401 still ends the session.
async function req(base: string, path: string, opts: RequestInit = {}, quiet = false): Promise<any> {
  // Mock-first: with VITE_MOCK=1 the whole app runs on fixtures, no backend needed.
  if (isMock()) {
    const body = opts.body ? JSON.parse(opts.body as string) : undefined
    try {
      return await mockRequest((opts.method as string) || 'GET', path, body)
    } catch (e: any) {
      // Mock validation failures (duplicate username, ...) surface like real ones.
      if (!quiet) toast(e.message)
      throw new ApiError(e.status ?? 500, e.message)
    }
  }
  // Credential endpoints take no token; anything else without one is "not signed in", which is
  // expected before login and must not fire requests or a "session expired" toast.
  const isAuthCall = path === '/api/login' || path.startsWith('/api/password-reset/')
  if (!token && !isAuthCall) throw new ApiError(401, '', true)
  try {
    const headers: any = { ...(opts.headers || {}) }
    if (token && !isAuthCall) headers['Authorization'] = `Bearer ${token}`   // credential calls never carry a (possibly stale or wrong-plane) session
    if (opts.body) headers['Content-Type'] = 'application/json'
    const res = await fetch(base + path, { ...opts, headers })
    if (res.status === 401 && !isAuthCall) {
      // A 401 on a call that carried our token = the session is gone (expired, revoked, account or
      // organization disabled: the server answers "session ended"). On login itself a 401 just
      // means wrong credentials, so it falls through and shows the server's message.
      setToken(null)
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
      throw new ApiError(401, SESSION_ENDED)
    }
    if (!res.ok) {
      let detail = res.statusText
      try {
        detail = (await res.json()).detail || detail
      } catch {}
      // Not an error to show: the password was right and the login form must now ask for the code.
      if (detail === 'mfa_required') throw new ApiError(res.status, detail, true)
      // Not an error either: the forced password dialog opens instead (see auth.tsx / App.tsx).
      if (detail === 'password_change_required') {
        window.dispatchEvent(new Event(PASSWORD_CHANGE_EVENT))
        throw new ApiError(res.status, 'Choose a new password to continue.', true)
      }
      throw new ApiError(res.status, detail)
    }
    const ct = res.headers.get('content-type') || ''
    return ct.includes('application/json') ? res.json() : res
  } catch (e) {
    // Every failure surfaces somewhere, even at call sites that never bothered with a .catch()
    // (most of them didn't, before this) - a network drop or a 500 used to fail completely
    // silently: the page just stayed on "Loading..." forever with zero explanation. Call sites
    // can still add their own .catch() for state rollback; they just don't have to for the
    // user to find out something went wrong.
    if (e instanceof ApiError && e.silent) throw e
    if (quiet && !(e instanceof ApiError && e.status === 401)) throw e
    const msg = e instanceof ApiError ? e.message : 'Network error - check your connection.'
    toast(msg)
    throw e
  }
}

const send = (method: string, body?: any): RequestInit => ({ method, body: body ? JSON.stringify(body) : undefined })

export const api = {
  get: (p: string) => req(PUBLIC, p),
  post: (p: string, body?: any) => req(PUBLIC, p, send('POST', body)),
  put: (p: string, body?: any) => req(PUBLIC, p, send('PUT', body)),
  pget: (p: string) => req(PRIVATE, p),
  ppost: (p: string, body?: any) => req(PRIVATE, p, send('POST', body)),
  pput: (p: string, body?: any) => req(PRIVATE, p, send('PUT', body)),
  publicBase: PUBLIC,
  privateBase: PRIVATE,
}

// Clients live on the public plane; staff and the system administrator on the private one (NFR-24).
const isTeam = (role?: string | null) => role !== 'client'
const plane = (role?: string | null) =>
  isTeam(role) ? { get: api.pget, post: api.ppost, put: api.pput, base: PRIVATE } : { get: api.get, post: api.post, put: api.put, base: PUBLIC }

// Keep the session alive. Stores the new token; failures other than 401 stay silent (the caller ignores them).
// Returns the fresh token WITHOUT storing it: the caller decides whether it is still wanted.
export async function refresh(role?: string | null): Promise<string> {
  const { token: t } = await req(plane(role).base, '/api/refresh', send('POST'), true)
  return t
}

// The old session dies on a password change, so the response's token must replace it.
export async function changePassword(role: string | null | undefined, current: string, next: string) {
  const r = await plane(role).post('/api/password', { current, new: next })
  if (r?.token) setToken(r.token)
  return r
}

export type Profile = {
  username: string; role: string; org_name: string | null
  display_name: string | null; email: string | null; phone: string | null; totp_enabled: boolean
}
export const profile = {
  get: (role?: string | null): Promise<Profile> => plane(role).get('/api/profile'),
  update: (role: string | null | undefined, body: { display_name?: string; phone?: string }) => plane(role).put('/api/profile', body),
  requestEmail: (role: string | null | undefined, email: string): Promise<{ ok: boolean; emailed: boolean }> =>
    plane(role).post('/api/profile/email', { email }),
  confirmEmail: (role: string | null | undefined, token: string) => plane(role).post('/api/profile/email/confirm', { token }),
}

export type Org = { id: string; name: string; status: string; created_at: string }
export type Account = {
  username: string; role: string; org_id: string | null; display_name: string | null; email: string | null
  disabled: number | boolean; totp_enabled: number | boolean; must_change_password: number | boolean; created_at: string
}
export type NewAccount = { username: string; role: string; org_id?: string; display_name?: string; email?: string }
const acct = (u: string) => `/api/sysadmin/accounts/${encodeURIComponent(u)}`
// System administrator console: private plane only.
export const sysadmin = {
  orgs: (): Promise<Org[]> => api.pget('/api/sysadmin/orgs'),
  createOrg: (name: string): Promise<{ id: string; name: string }> => api.ppost('/api/sysadmin/orgs', { name }),
  setOrg: (id: string, enabled: boolean) => api.ppost(`/api/sysadmin/orgs/${encodeURIComponent(id)}/${enabled ? 'enable' : 'disable'}`),
  accounts: (): Promise<Account[]> => api.pget('/api/sysadmin/accounts'),
  createAccount: (body: NewAccount): Promise<{ username: string; role: string; temp_password: string }> => api.ppost('/api/sysadmin/accounts', body),
  resetPassword: (u: string): Promise<{ temp_password: string }> => api.ppost(`${acct(u)}/reset-password`),
  resetMfa: (u: string) => api.ppost(`${acct(u)}/reset-mfa`),
  setDisabled: (u: string, disabled: boolean) => api.ppost(`${acct(u)}/${disabled ? 'disable' : 'enable'}`),
  setRole: (u: string, role: string) => api.pput(`${acct(u)}/role`, { role }),
  setEmail: (u: string, email: string) => api.pput(`${acct(u)}/email`, { email }),
}
// Tasks (step 2): the client's scan requests, in the client vocabulary (no staff names or comments).
export type TaskStatus = 'waiting' | 'accepted' | 'scheduled' | 'scanning' | 'paused' | 'in_review' | 'delivered' | 'declined' | 'expired'
export type ClientTask = {
  id: string; target: string; path: string; port: number | null; notes: string; scan_mode: 'local' | 'cloud'
  status: TaskStatus; when: string; reason: string | null; job_id: string | null
  not_before: string; not_after: string; scheduled_at: string | null
}
export type TimelineItem = { status: TaskStatus; at: string; note?: string }
export type NewTask = { target: string; path: string; port?: number; notes: string; not_before: string; not_after: string; scan_mode: 'local' | 'cloud' }
const task = (id: string) => `/api/tasks/${encodeURIComponent(id)}`
export const tasks = {
  list: (): Promise<ClientTask[]> => api.get('/api/tasks'),
  get: (id: string): Promise<ClientTask & { timeline: TimelineItem[] }> => api.get(task(id)),
  create: (t: NewTask): Promise<ClientTask> => api.post('/api/tasks', t),
  timeline: (id: string): Promise<TimelineItem[]> => api.get(`${task(id)}/events`),
}

// Staff (private plane): the role-scoped board and the one transition route.
export type TaskAction = { to: string; kind: string; comment: boolean; allowed: boolean; why: string | null }
export type BoardCard = {
  id: string; version: number; stage: string; scanState: string | null; client: string; target: string; scanMode: string
  sev: { c: number; h: number; m: number; l: number }; meta: string
  startsAt?: string | null; submittedAt?: string | null; deliveredAt?: string | null; assignee: string | null; jobId: string | null
  suspended: boolean; reason: string | null; actions: TaskAction[]
}
export type BoardColumn = { id: string; title: string; accent: string; more?: number; cards: BoardCard[] }
export type TaskEvent = { id: number; from_stage: string | null; from_scan_state: string | null; to_stage: string; to_scan_state: string | null; actor: string; comment: string | null; at: string }
export type TaskDetail = {
  task: { id: string; target: string; path: string; port: number | null; notes: string; scan_mode: string; not_before: string; not_after: string
    max_minutes: number | null; scheduled_at: string | null; assignee: string | null; suspend_reason: string | null
    decline_cause: string | null; stage: string; scan_state: string | null; version: number; job_id: string | null }
  report_id: string | null; can_edit_report: boolean; versions: { version_no: number; editor: string; note: string; created_at: string }[]
}
export type MoveBody = { to: string; version: number; comment?: string; scheduled_at?: string; max_minutes?: number; opts?: Record<string, unknown> }
export const team = {
  board: (): Promise<BoardColumn[]> => api.pget('/api/board'),
  move: (id: string, body: MoveBody): Promise<{ id: string; stage: string; scan_state: string | null; version: number }> =>
    api.ppost(`${task(id)}/transition`, body),
  detail: (id: string): Promise<TaskDetail> => api.pget(`${task(id)}/detail`),
  events: (id: string): Promise<TaskEvent[]> => api.pget(`${task(id)}/events`),
}


// Fake progression for VITE_MOCK=1 so the live-progress UI stays demoable without a backend -
// mirrors the real phase-boundary cadence (katana -> nuclei -> sqlmap -> done) on a timer.
function mockStreamEvents(onMessage: (data: any) => void): () => void {
  const steps = [
    { status: 'running', per_tool_status: { katana: 'running' } },
    { status: 'running', per_tool_status: { katana: 'done', nuclei: 'running' } },
    { status: 'running', per_tool_status: { katana: 'done', nuclei: 'done', sqlmap: 'running' } },
    { status: 'done', per_tool_status: { katana: 'done', nuclei: 'done', sqlmap: 'done' } },
  ]
  const timers = steps.map((s, i) => setTimeout(() => onMessage(s), 1300 * (i + 1)))
  return () => timers.forEach(clearTimeout)
}

// Live scan progress (GET .../events, text/event-stream). Deliberately NOT the native
// EventSource API: EventSource can't set an Authorization header, and this app has no other
// way to authenticate. A manual fetch + ReadableStream reader can set headers like any other
// request, at the cost of parsing "data: {...}\n\n" frames by hand. Returns a cleanup function
// (abort the underlying fetch) - call it on unmount/target change.
export function streamEvents(base: string, path: string, onMessage: (data: any) => void): () => void {
  if (isMock()) return mockStreamEvents(onMessage)

  const controller = new AbortController()
  ;(async () => {
    try {
      const headers: any = {}
      if (token) headers['Authorization'] = `Bearer ${token}`
      const res = await fetch(base + path, { headers, signal: controller.signal })
      if (!res.ok || !res.body) return
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() || ''
        for (const part of parts) {
          const line = part.split('\n').find((l) => l.startsWith('data: '))
          if (line) {
            try { onMessage(JSON.parse(line.slice(6))) } catch {}
          }
        }
      }
    } catch {
      // Aborted on cleanup, or a network error - either way this stream just quietly stops
      // contributing; it's a progress enhancement, not the only source of truth for the page.
    }
  })()
  return () => controller.abort()
}

// Multipart upload (a reviewer's edited .docx). Same failure handling as req(): a 401 ends the
// session, other errors surface the server's message.
export async function upload(base: string, path: string, file: File): Promise<any> {
  if (isMock()) return { ok: true }
  if (!token) throw new ApiError(401, '', true)
  try {
    const fd = new FormData()
    fd.append('file', file)
    const res = await fetch(base + path, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: fd })
    if (res.status === 401) {
      setToken(null)
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
      throw new ApiError(401, SESSION_ENDED)
    }
    if (!res.ok) {
      let detail = res.statusText
      try { detail = (await res.json()).detail || detail } catch {}
      if (detail === 'password_change_required') {
        window.dispatchEvent(new Event(PASSWORD_CHANGE_EVENT))
        throw new ApiError(res.status, 'Choose a new password to continue.', true)
      }
      throw new ApiError(res.status, detail)
    }
    return res.json()
  } catch (e) {
    if (e instanceof ApiError && e.silent) throw e
    toast(e instanceof ApiError ? e.message : 'Network error - check your connection.')
    throw e
  }
}

export async function download(base: string, path: string, filename: string) {
  // Bypasses req() (needs a raw Response to read as a blob, not JSON), so it needs its own
  // copy of the same failure handling - otherwise a failed download (file missing, report not
  // delivered yet) throws silently and call sites that don't await this (most don't; it's
  // normally fired from an onClick) never find out, while any "Downloaded ✓" state they set
  // optimistically stays wrong.
  try {
    const headers: any = {}
    if (token) headers['Authorization'] = `Bearer ${token}`
    const res = await fetch(base + path, { headers })
    if (res.status === 401 && token) {
      setToken(null)
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
      throw new ApiError(401, SESSION_ENDED)
    }
    if (!res.ok) {
      let detail = res.statusText
      try {
        detail = (await res.json()).detail || detail
      } catch {}
      throw new ApiError(res.status, detail)
    }
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    if (e instanceof ApiError && e.silent) throw e
    const msg = e instanceof ApiError ? e.message : 'Network error - check your connection.'
    toast(msg)
    throw e
  }
}
