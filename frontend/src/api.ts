// API client: JWT bearer + two base URLs (public plane, private/Tailscale plane).
// Public defaults to same-origin ('' -> /api proxied by Vite/Caddy); private defaults to the
// dev port and is set to the Tailscale host in production via VITE_PRIVATE_API.

import { isMock, mockRequest } from './mock'

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
  constructor(public status: number, message: string) {
    super(message)
  }
}

async function req(base: string, path: string, opts: RequestInit = {}): Promise<any> {
  // Mock-first: with VITE_MOCK=1 the whole app runs on fixtures, no backend needed.
  if (isMock()) {
    const body = opts.body ? JSON.parse(opts.body as string) : undefined
    return mockRequest((opts.method as string) || 'GET', path, body)
  }
  const headers: any = { ...(opts.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (opts.body) headers['Content-Type'] = 'application/json'
  const res = await fetch(base + path, { ...opts, headers })
  if (res.status === 401) {
    setToken(null)
    throw new ApiError(401, 'session expired, please log in again')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch {}
    throw new ApiError(res.status, detail)
  }
  const ct = res.headers.get('content-type') || ''
  return ct.includes('application/json') ? res.json() : res
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

export async function download(base: string, path: string, filename: string) {
  const headers: any = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(base + path, { headers })
  if (!res.ok) throw new ApiError(res.status, 'download failed')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
