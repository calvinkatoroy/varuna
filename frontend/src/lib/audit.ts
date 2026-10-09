import { api, download } from '@/api'
import type { Sev } from './findings'

export type PdfStatus = 'queued' | 'rendering' | 'converting' | 'ready' | 'failed'
export type PdfJob = {
  id: string; n: number | null; status: PdfStatus; filename: string | null; content_version: number
  error: string | null; requested_by: string; created_at: string; updated_at: string
}
export type PdfSummary = { current: boolean; latest: PdfJob | null; active: PdfJob | null; history: PdfJob[] }
export type AuditCounts = { total: number; tp: number; fp: number; manual: number; severity: Record<Sev, number> }
export type AuditSummary = {
  task: { id: string; target: string; stage: string; version: number; client: string; assignee: string | null }
  can_audit: boolean; ai_chat: boolean; content_version: number; counts: AuditCounts; pdf: PdfSummary
}
export type PreviewFinding = {
  id: string; _id: string; name: string; severity: string; host: string; url: string; impact: string | null
  remediation: string | null; description: string | null; cve: string | null; cwe: string | null; tool: string | null
  verdict: string; evidence: string | null
}
export type PreviewItem =
  | { kind: 'paragraph' | 'bullet'; text: string }
  | { kind: 'cover'; client: string; target: string; ref: string }
  | { kind: 'counts'; counts: Record<string, number>; risk: string }
  | { kind: 'kv'; rows: string[][] }
  | { kind: 'table'; header: string[]; rows: (string | number)[][]; sev_col: number | null }
  | { kind: 'finding'; f: PreviewFinding }
export type PreviewSection = { id: string; title: string; items: PreviewItem[] }
export type ContentVersion = { version: number; created_by: string; note: string; created_at: string }
export type ContentView = { version: number; created_by: string; created_at: string; note: string; preview: PreviewSection[]; versions: ContentVersion[] }
export type TrailRow = { id: number; actor: string; action: string; subject: string; detail: Record<string, any>; at: string }
export type DiffRow = { op: string; where: string; before: string | null; after: string | null; sanitized: boolean }
export type AiTurn = {
  id: string; actor: string; prompt: string; status: 'queued' | 'running' | 'ready' | 'failed'; summary: string | null
  error: string | null; base_version: number; applied: boolean; applied_version: number | null; outdated: boolean
  diff: DiffRow[]; created_at: string; updated_at: string
}
export type ManualForm = {
  name: string; severity: Sev; host: string; url: string; description: string; evidence: string; impact: string; remediation: string
}
export const EMPTY_MANUAL: ManualForm = { name: '', severity: 'medium', host: '', url: '', description: '', evidence: '', impact: '', remediation: '' }

// ---- pure helpers ----
export const PDF_ACTIVE: PdfStatus[] = ['queued', 'rendering', 'converting']
export const isPdfActive = (s?: PdfStatus | null): boolean => !!s && PDF_ACTIVE.includes(s)
export const PDF_STEPS = ['Waiting to start', 'Building the report', 'Converting to PDF', 'Ready'] as const
export const pdfStep = (s: PdfStatus): number => ({ queued: 0, rendering: 1, converting: 2, ready: 3, failed: 3 }[s])
/** Poll gap in ms: 1.5 s at first, easing to 4 s. */
export const nextDelay = (attempt: number): number => Math.min(4000, 1500 + attempt * 500)
export const PROMPT_MAX = 1000
/** Hard stop for watching one PDF job. The server gives up on a silent job after 300 s, so this is a little longer. */
export const PDF_POLL_MAX_MS = 360_000
export const pollExpired = (startedAt: number, now: number, maxMs: number): boolean => now - startedAt >= maxMs
/** The report changed after the newest ready PDF was built (the server says `current: false`). Submit is blocked until a new one. */
export const pdfStale = (p: PdfSummary): boolean => !!p.latest && !p.current && !p.active
/** Passwords are masked until the person asks. The mask has a fixed length so it does not leak the real one. */
export const maskPw = (pw: string, shown: boolean): string => (shown ? pw : '•'.repeat(12))

/** Why the Generate button is disabled, or null. `busy` covers the moment between the click and the answer. */
export function generateBlockedReason(sum: AuditSummary | null, busy: boolean): string | null {
  if (!sum) return 'Loading'
  if (!sum.can_audit) return 'Only the assignee or a lead pentester can generate the PDF'
  if (busy || sum.pdf.active) return 'A PDF is being prepared'
  if (sum.pdf.current) return 'The PDF is already up to date'
  return null
}
export function pdfBadge(p: PdfSummary): { label: string; tone: 'low' | 'med' | 'info' } {
  if (p.active) return { label: 'PDF in progress', tone: 'info' }
  if (p.current && p.latest) return { label: `PDF ${p.latest.n} is up to date`, tone: 'low' }
  if (p.latest) return { label: 'PDF out of date', tone: 'med' }
  return { label: 'No PDF yet', tone: 'med' }
}
export type ManualProblem = { field: 'name' | 'description' | 'url'; msg: string }
export function manualProblem(f: ManualForm): ManualProblem | null {
  if (!f.name.trim()) return { field: 'name', msg: 'Give the finding a name' }
  if (f.name.trim().length > 300) return { field: 'name', msg: 'The name is too long (300 characters at most)' }
  if (!f.description.trim()) return { field: 'description', msg: 'Describe what you found' }
  if (f.url.length > 2048) return { field: 'url', msg: 'The URL is too long' }
  return null
}
export const validateManual = (f: ManualForm): string | null => manualProblem(f)?.msg ?? null

/** The second line of an audit-trail row, from what the server stored in `detail`. */
export function trailDetail(r: TrailRow): string {
  const d = r.detail ?? {}
  const name = typeof d.name === 'string' ? d.name : ''
  switch (r.action) {
    case 'verdict': {
      const what = d.verdict === 'fp' ? 'marked false positive' : d.verdict === 'tp' ? 'confirmed' : 'verdict changed'
      return name ? `${name}: ${what}` : what
    }
    case 'finding_edit': {
      const before = (d.before ?? {}) as Record<string, string>
      const after = (d.after ?? {}) as Record<string, string>
      const fields = Object.keys(after).map((k) => (k === 'severity' && before.severity ? `severity ${before.severity} to ${after.severity}` : k))
      return `${name || 'Finding'}: changed ${fields.join(', ') || 'text'}`
    }
    case 'manual_add': return [name, d.severity].filter(Boolean).join(' · ')
    case 'content_restore': return `Version ${r.subject} restored as version ${d.new_version ?? '?'}`
    case 'pdf_requested': return d.content_version ? `Built from report version ${d.content_version}` : ''
    default: return name
  }
}
/** Bullets that follow each other become one list. */
export type Grouped = PreviewItem | { kind: 'list'; items: string[] }
export function groupItems(items: PreviewItem[]): Grouped[] {
  const out: Grouped[] = []
  for (const it of items) {
    const last = out[out.length - 1]
    if (it.kind === 'bullet') {
      if (last && last.kind === 'list') last.items.push(it.text)
      else out.push({ kind: 'list', items: [it.text] })
    } else out.push(it)
  }
  return out
}
export const turnActive = (t: AiTurn): boolean => t.status === 'queued' || t.status === 'running'
export function promptBlockedReason(prompt: string, busy: boolean): string | null {
  if (busy) return 'Wait for the current suggestion'
  if (!prompt.trim()) return 'Write what you want changed'
  if (prompt.length > PROMPT_MAX) return `Keep it under ${PROMPT_MAX} characters`
  return null
}
export function canApplyTurn(t: AiTurn, contentVersion: number, canAudit: boolean): string | null {
  if (!canAudit) return 'Only the assignee or a lead pentester can apply changes'
  if (t.applied) return 'Already applied'
  if (t.status !== 'ready') return 'Not ready'
  if (!t.diff.length) return 'This suggestion makes no change'
  if (t.outdated || t.base_version !== contentVersion) return 'The report changed. Ask again.'
  return null
}
/** Why the report cannot be changed here (page note and chat panel), or null when the person may change it. */
export function readOnlyReason(s: AuditSummary): string | null {
  if (s.can_audit) return null
  return s.task.stage !== 'completed'
    ? 'This report is in review and cannot be changed here. To change it, the task has to be sent back to Completed.'
    : 'Only the assignee or a lead pentester can change this report.'
}
export const ACTION_LABEL: Record<string, string> = {
  verdict: 'Changed a verdict', finding_edit: 'Edited a finding', manual_add: 'Added a finding', pdf_requested: 'Generated a PDF',
  content_apply: 'Applied an AI suggestion', content_restore: 'Restored a version', password_view: 'Viewed the PDF password',
}

// ---- API (private plane) ----
const base = (tid: string) => `/api/tasks/${encodeURIComponent(tid)}`
const enc = encodeURIComponent
export const auditApi = {
  summary: (tid: string): Promise<AuditSummary> => api.pget(`${base(tid)}/audit`),
  content: (tid: string): Promise<ContentView> => api.pget(`${base(tid)}/report/content`),
  trail: (tid: string): Promise<TrailRow[]> => api.qpget(`${base(tid)}/audit/trail`),
  restore: (tid: string, version: number, base_version: number): Promise<{ version: number }> =>
    api.ppost(`${base(tid)}/report/restore`, { version, base_version }),
  verdict: (fid: string, verdict: 'tp' | 'fp') => api.ppost(`/api/findings/${enc(fid)}/verdict`, { verdict }),
  edit: (tid: string, fid: string, body: Partial<{ severity: string; impact: string; remediation: string }>) =>
    api.ppost(`${base(tid)}/findings/${enc(fid)}/edit`, body),
  addManual: (tid: string, f: ManualForm): Promise<{ id: string }> => api.ppost(`${base(tid)}/findings/manual`, f),
  generate: (tid: string): Promise<{ job: PdfJob }> => api.qppost(`${base(tid)}/report/generate`),
  job: (tid: string, jid: string): Promise<PdfJob> => api.qpget(`${base(tid)}/report/jobs/${enc(jid)}`),
  password: (tid: string): Promise<{ password: string }> => api.qpget(`${base(tid)}/report/password`),
  downloadPdf: (tid: string, job: PdfJob) =>
    download(api.privateBase, `${base(tid)}/report/pdfs/${enc(job.id)}/download`, job.filename ?? 'Pentest_Report.pdf'),
  turns: (tid: string): Promise<AiTurn[]> => api.qpget(`${base(tid)}/ai/turns`),
  turn: (tid: string, id: string): Promise<AiTurn> => api.qpget(`${base(tid)}/ai/turns/${enc(id)}`),
  ask: (tid: string, prompt: string): Promise<{ turn: AiTurn }> => api.ppost(`${base(tid)}/ai/turns`, { prompt }),
  apply: (tid: string, id: string, base_version: number): Promise<{ version: number }> =>
    api.ppost(`${base(tid)}/ai/turns/${enc(id)}/apply`, { base_version }),
}
