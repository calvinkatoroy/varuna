// Mock API router: maps "METHOD /path" to a fixture so the whole app runs with no backend
// (VITE_MOCK=1). Adds small latency for realism. api.ts routes through here when mock is on.
import * as fx from './fixtures'

const routes: Record<string, any> = {
  'GET /api/me': fx.me,
  'POST /api/login': { token: 'mock.jwt.client' },
  'POST /api/register': { token: 'mock.jwt.client' },
  'GET /api/cockpit': fx.cockpit,
  'GET /api/proposals': fx.engagements,
  'GET /api/agent': { registered: true, online: true },
  'GET /api/pipeline/board': fx.board,
  'GET /api/pipeline/detail/r1': fx.engagementDetail.r1,
  'GET /api/findings': fx.findings,
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

export function isMock(): boolean {
  return String((import.meta as any).env?.VITE_MOCK ?? '1') === '1'
}

export async function mockRequest(method: string, path: string, _body?: any): Promise<any> {
  await delay(160)
  const key = `${method.toUpperCase()} ${path}`
  if (key in routes) return routes[key]
  // POST actions (submit proposal, forward, etc.) succeed optimistically in the prototype.
  if (method.toUpperCase() === 'POST') return { ok: true, id: 'mock-' + Math.random().toString(36).slice(2, 8) }
  return {}
}
