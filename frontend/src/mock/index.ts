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

// Team accounts are provisioned, not self-registered (only clients register via AuthGate).
// Any password is accepted here, same as the client login - this is a mock, not real auth.
const teamAccounts: Record<string, { username: string; name: string; role: string }> = {
  admin: { username: 'admin', name: 'Admin', role: 'lead_pentester' },
  riyan: { username: 'riyan', name: 'Riyan', role: 'lead_pentester' },
  dimas: { username: 'dimas', name: 'Dimas', role: 'pentester' },
  aisah: { username: 'aisah', name: 'Aisah', role: 'reporter' },
  hani: { username: 'hani', name: 'Hani', role: 'governance' },
}
let currentUser: { username: string; name: string; role: string } = fx.me

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

  if (m === 'GET' && path === '/api/me') return currentUser
  if (m === 'POST' && path === '/api/login') {
    const acct = teamAccounts[String(body?.username ?? '').toLowerCase()]
    currentUser = acct ?? fx.me
    return { token: 'mock.jwt.' + currentUser.role }
  }
  if (m === 'POST' && path === '/api/password') return { ok: true }
  if (m === 'POST' && path === '/api/register') {
    currentUser = fx.me
    return { token: 'mock.jwt.client' }
  }
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
