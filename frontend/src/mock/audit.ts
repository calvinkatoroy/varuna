// VITE_MOCK=1 handlers for the audit page: PDF jobs progress by elapsed time, the AI answers with a canned patch.
import type { AiTurn, AuditSummary, ContentView, PdfJob, PdfStatus } from '@/lib/audit'

const fail = (status: number, message: string) => Object.assign(new Error(message), { status })
let version = 1
const versions = [{ version: 1, created_by: 'system', note: 'Dibuat dari hasil pemindaian', created_at: '2026-10-09 08:00:00' }]
const jobs: { id: string; n: number; t0: number; cv: number }[] = []
const turns: AiTurn[] = []
const trail: any[] = []
let nid = 1

const statusAt = (t0: number): PdfStatus => { const d = Date.now() - t0; return d < 1200 ? 'queued' : d < 2600 ? 'rendering' : d < 4200 ? 'converting' : 'ready' }
const job = (j: (typeof jobs)[number]): PdfJob => {
  const status = statusAt(j.t0)
  return { id: j.id, n: status === 'ready' ? j.n : null, status, filename: status === 'ready' ? `PT_Samudera_Logistik_portal_samudera_co_id_Pentest_Report_${j.n}.pdf` : null,
    content_version: j.cv, error: null, requested_by: 'dimas', created_at: '2026-10-09 08:00:00', updated_at: '2026-10-09 08:00:00' }
}
const summary = (tid: string): AuditSummary => {
  const all = jobs.map(job).reverse()
  const latest = all.find((j) => j.status === 'ready') ?? null
  return {
    task: { id: tid, target: 'https://portal.samudera.co.id', stage: 'completed', version: 1, client: 'PT Samudera Logistik', assignee: 'dimas' },
    can_audit: true, ai_chat: true, content_version: version, counts: { total: 18, tp: 16, fp: 2, manual: 0, severity: { critical: 3, high: 5, medium: 4, low: 3, info: 1 } },
    pdf: { current: !!latest && latest.content_version === version, latest, active: all.find((j) => j.status !== 'ready' && j.status !== 'failed') ?? null, history: all },
  }
}
const content = (): ContentView => ({
  version, created_by: 'dimas', created_at: '2026-10-09 08:00:00', note: '', versions: [...versions].reverse(),
  preview: [
    { id: 'executive_summary', title: 'Ringkasan Eksekutif', items: [
      { kind: 'paragraph', text: 'Varuna melakukan penilaian kerentanan aplikasi web secara otomatis pada portal.samudera.co.id untuk PT Samudera Logistik.' },
      { kind: 'counts', counts: { critical: 3, high: 5, medium: 4, low: 3, info: 1 }, risk: 'Critical' }] },
    { id: 'methodology', title: 'Metodologi', items: [{ kind: 'bullet', text: 'Penemuan: aplikasi ditelusuri (crawl).' }, { kind: 'bullet', text: 'Deteksi: pemeriksaan kerentanan umum dijalankan.' }] },
    { id: 'findings', title: 'Temuan Rinci', items: [] },
  ],
})

export function auditRoute(m: string, path: string, body: any): any {
  const u = path.match(/^\/api\/tasks\/([^/]+)\/(.*)$/)
  if (!u) return undefined
  const [, tid, rest] = u
  if (m === 'GET' && rest === 'audit') return summary(tid)
  if (m === 'GET' && rest === 'audit/trail') return [...trail].reverse()
  if (m === 'GET' && rest === 'report/content') return content()
  if (m === 'POST' && rest === 'report/restore') { version += 1; versions.push({ version, created_by: 'dimas', note: `Restored version ${body.version}`, created_at: '2026-10-09 09:00:00' }); return { version } }
  if (m === 'POST' && rest === 'report/generate') {
    const s = summary(tid).pdf
    if (s.active) return { job: s.active }
    if (s.current && s.latest) return { job: s.latest }
    const j = { id: 'job-' + nid++, n: jobs.length + 1, t0: Date.now(), cv: version }
    jobs.push(j)
    trail.push({ id: trail.length + 1, actor: 'dimas', action: 'pdf_requested', subject: j.id, detail: {}, at: '2026-10-09 09:00:00' })
    return { job: job(j) }
  }
  const jb = m === 'GET' && rest.match(/^report\/jobs\/([^/]+)$/)
  if (jb) { const j = jobs.find((x) => x.id === jb[1]); if (!j) throw fail(404, 'no such job'); return job(j) }
  if (m === 'GET' && rest === 'report/password') return { password: 'Kp7-mock-ZQ3x' }
  if (m === 'POST' && rest === 'findings/manual') {
    trail.push({ id: trail.length + 1, actor: 'dimas', action: 'manual_add', subject: 'mock-m1', detail: { name: body?.name ?? '' }, at: '2026-10-09 09:00:00' })
    return { id: 'mock-m1' }
  }
  if (m === 'POST' && /^findings\/[^/]+\/edit$/.test(rest)) {
    trail.push({ id: trail.length + 1, actor: 'dimas', action: 'finding_edit', subject: rest.split('/')[1], detail: {}, at: '2026-10-09 09:00:00' })
    return { ok: true }
  }
  if (m === 'GET' && rest === 'ai/turns') return turns
  const one = m === 'GET' && rest.match(/^ai\/turns\/([^/]+)$/)
  if (one) {
    const t = turns.find((x) => x.id === one[1]); if (!t) throw fail(404, 'no such suggestion')
    if (t.status !== 'ready' && Date.now() - Date.parse(t.created_at) > 3500) {
      t.status = 'ready'; t.summary = 'Ringkasan eksekutif dipersingkat'
      t.diff = [{ op: 'replace_text', where: 'Ringkasan Eksekutif', before: 'Varuna melakukan penilaian kerentanan aplikasi web secara otomatis pada portal.samudera.co.id untuk PT Samudera Logistik.', after: 'Varuna menguji portal.samudera.co.id untuk PT Samudera Logistik.', sanitized: false }]
    }
    t.outdated = !t.applied && t.base_version !== version
    return t
  }
  if (m === 'POST' && rest === 'ai/turns') {
    const t: AiTurn = { id: 'turn-' + nid++, actor: 'dimas', prompt: body.prompt, status: 'running', summary: null, error: null, base_version: version, applied: false,
      applied_version: null, outdated: false, diff: [], created_at: new Date().toISOString(), updated_at: '' }
    turns.push(t)
    return { turn: t }
  }
  const ap = m === 'POST' && rest.match(/^ai\/turns\/([^/]+)\/apply$/)
  if (ap) {
    const t = turns.find((x) => x.id === ap[1]); if (!t) throw fail(404, 'no such suggestion')
    if (t.applied || t.base_version !== version) throw fail(409, 'The report changed since this suggestion. Ask again.')
    version += 1; t.applied = true; t.applied_version = version; t.diff = []
    versions.push({ version, created_by: 'dimas', note: 'AI: ' + t.summary, created_at: '2026-10-09 09:05:00' })
    return { version }
  }
  return undefined
}
