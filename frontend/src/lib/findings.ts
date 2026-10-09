import { api } from '@/api'
import { cacheGet, cacheKeys, cacheSet } from './swr'

export type Plane = 'pub' | 'prv'
export const SEVS = ['critical', 'high', 'medium', 'low', 'info'] as const
export type Sev = (typeof SEVS)[number]
export type Counts = Record<Sev, number>
export const PAGE = 100

export const SEV_LABEL: Record<Sev, string> = { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low', info: 'Info' }
export const SEV_LETTER: Record<Sev, string> = { critical: 'C', high: 'H', medium: 'M', low: 'L', info: 'I' }
export const SEV_CHIP: Record<Sev, string> = {
  critical: 'bg-crit-bg text-crit', high: 'bg-high-bg text-high', medium: 'bg-med-bg text-med', low: 'bg-low-bg text-low', info: 'bg-panel text-ink',
}
// The colour tokens are --color-crit / --color-med; --color-critical draws nothing.
export const sevVar = (s: string): string => ({ critical: 'crit', medium: 'med' } as Record<string, string>)[s] ?? s

export type TargetRow = {
  task_id: string; target: string; total: number; fixed: number; scanned_at: string; counts: Counts
  org_name?: string; fp?: number   // staff only
}
export type FindingRow = {
  id: string; task_id: string; name: string; severity: string; host: string; url: string; tool: string
  cve?: string | null; cwe?: string | null; verdict: 'tp' | 'fp'; status: string
}
export type FindingFull = FindingRow & { evidence: string; remediation?: string | null; description?: string | null; impact?: string | null; org_name?: string }
export type FindingsPage = { items: FindingRow[]; next_cursor: string | null; total: number }
/** What the cache holds for one open target (and severity filter): the loaded rows and where to continue. */
export type RowsState = { items: FindingRow[]; next: string | null; total: number }

type PageOpts = { cursor?: string | null; upto?: string | null; severity?: string | null }

export function pageParams(taskId: string, o: PageOpts = {}): string {
  const q = new URLSearchParams({ task_id: taskId, limit: String(PAGE) })
  if (o.cursor) q.set('cursor', o.cursor)
  if (o.upto) q.set('upto', o.upto)
  if (o.severity) q.set('severity', o.severity)
  return q.toString()
}

// Quiet reads: the panels render their own error and "not found" states, so no toast on top.
const read = (plane: Plane, path: string) => (plane === 'pub' ? api.qget(path) : api.qpget(path))
export const findingsApi = (plane: Plane) => ({
  page: (taskId: string, o: PageOpts = {}): Promise<FindingsPage> => read(plane, `/api/findings?${pageParams(taskId, o)}`),
  one: (id: string): Promise<FindingFull> => read(plane, `/api/findings/id/${encodeURIComponent(id)}`),
})

/** Append a page; a row that is already loaded (re-correlation between requests) is not shown twice. */
export function mergeRows(prev: FindingRow[], more: FindingRow[]): FindingRow[] {
  const seen = new Set(prev.map((f) => f.id))
  return [...prev, ...more.filter((f) => !seen.has(f.id))]
}

/** Portfolio numbers for the summary, from the targets list (never from loaded rows). */
export function totalsOf(rows: TargetRow[]) {
  const counts: Counts = { critical: 0, high: 0, medium: 0, low: 0, info: 0 }
  let total = 0
  let fixed = 0
  for (const t of rows) {
    total += t.total
    fixed += t.fixed
    for (const s of SEVS) counts[s] += t.counts[s]
  }
  return { counts, total, fixed, open: total - fixed }
}

/** Arrow-key movement between accordion headers (wraps); null = not a navigation key. */
export function nextHeaderIndex(key: string, i: number, n: number): number | null {
  if (key === 'ArrowDown') return (i + 1) % n
  if (key === 'ArrowUp') return (i - 1 + n) % n
  if (key === 'Home') return 0
  if (key === 'End') return n - 1
  return null
}

export const rowsKeyPrefix = (plane: Plane, taskId: string) => `${plane}:findings:${taskId}:`
export const rowsKey = (plane: Plane, taskId: string, severity: string | null) => rowsKeyPrefix(plane, taskId) + (severity ?? '')

/** Patch one loaded row in every cached view of its target (all severity filters); mounted panels follow. */
export function patchRows(plane: Plane, taskId: string, id: string, patch: Partial<FindingRow>): void {
  for (const k of cacheKeys(rowsKeyPrefix(plane, taskId))) {
    const s = cacheGet<RowsState>(k)
    if (s?.items.some((f) => f.id === id)) cacheSet(k, { ...s, items: s.items.map((f) => (f.id === id ? { ...f, ...patch } : f)) })
  }
}
