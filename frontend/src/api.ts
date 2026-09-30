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

const PUBLIC = (import.meta as any).env.VITE_PUBLIC_API || ''
const PRIVATE = (import.meta as any).env.VITE_PRIVATE_API || 'http://localhost:8010'

let token: string | null = localStorage.getItem('varuna_jwt')

export function setToken(t: string | null) {
  token = t
  if (t) localStorage.setItem('varuna_jwt', t)
  else localStorage.removeItem('varuna_jwt')
}
export function getToken() {
  return token
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public silent = false) {
    super(message)
  }
}

async function req(base: string, path: string, opts: RequestInit = {}): Promise<any> {
  // Mock-first: with VITE_MOCK=1 the whole app runs on fixtures, no backend needed.
  if (isMock()) {
    const body = opts.body ? JSON.parse(opts.body as string) : undefined
    return mockRequest((opts.method as string) || 'GET', path, body)
  }
  // Credential endpoints take no token; anything else without one is "not signed in", which is
  // expected before login and must not fire requests or a "session expired" toast.
  const isAuthCall = path === '/api/login' || path === '/api/register' || path.startsWith('/api/password-reset/')
  if (!token && !isAuthCall) throw new ApiError(401, '', true)
  try {
    const headers: any = { ...(opts.headers || {}) }
    if (token && !isAuthCall) headers['Authorization'] = `Bearer ${token}`   // credential calls never carry a (possibly stale or wrong-plane) session
    if (opts.body) headers['Content-Type'] = 'application/json'
    const res = await fetch(base + path, { ...opts, headers })
    if (res.status === 401 && !isAuthCall) {
      // A 401 on a call that carried our token = the session is gone. (On login itself a 401
      // just means wrong credentials, so it falls through and shows the server's message.)
      setToken(null)
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
      throw new ApiError(401, 'Session expired - please log in again.')
    }
    if (!res.ok) {
      let detail = res.statusText
      try {
        detail = (await res.json()).detail || detail
      } catch {}
      // Not an error to show: the password was right and the login form must now ask for the code.
      if (detail === 'mfa_required') throw new ApiError(res.status, detail, true)
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
    const msg = e instanceof ApiError ? e.message : 'Network error - check your connection.'
    toast(msg)
    throw e
  }
}

export const api = {
  get: (p: string) => req(PUBLIC, p),
  post: (p: string, body?: any) =>
    req(PUBLIC, p, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  pget: (p: string) => req(PRIVATE, p),
  ppost: (p: string, body?: any) =>
    req(PRIVATE, p, { method: 'POST', body: body ? JSON.stringify(body) : undefined }),
  publicBase: PUBLIC,
  privateBase: PRIVATE,
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
      throw new ApiError(401, 'Session expired - please log in again.')
    }
    if (!res.ok) {
      let detail = res.statusText
      try { detail = (await res.json()).detail || detail } catch {}
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
