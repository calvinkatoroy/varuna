// Placeholder data for the mock-first prototype. Shapes mirror the real API where an endpoint
// exists; the client-posture aggregates (posture/trend) are prototype-only until the backend
// client-findings aggregation lands (documented follow-up). Deliberately over-stuffed with rows
// so every page reads like a busy, real workspace rather than a 2-item demo.

export const me = { username: 'samudera', name: 'PT Samudera Logistik', role: 'client', org_id: 'org-samudera' }

// Engagements are the core entity of the portfolio cockpit. Each absorbs its target "asset":
// grade, severity breakdown, open/fixed counts, status. Click one to drill into its findings.
export const engagements = [
  { id: 'e1', target: 'api.acme.io', mode: 'advanced', status: 'in_review', grade: 'D', sev: { c: 1, h: 2, m: 1, l: 0 }, open: 4, fixed: 0, when: '2h ago' },
  { id: 'e2', target: 'acme.io', mode: 'standard', status: 'delivered', grade: 'A', sev: { c: 0, h: 0, m: 1, l: 1 }, open: 1, fixed: 1, when: 'Jun 18' },
  { id: 'e3', target: 'staging.acme.io', mode: 'standard', status: 'scanning', grade: 'C', sev: { c: 1, h: 1, m: 2, l: 1 }, open: 3, fixed: 2, when: 'now' },
  { id: 'e4', target: 'shop.acme.io', mode: 'standard', status: 'in_review', grade: 'C', sev: { c: 1, h: 2, m: 2, l: 1 }, open: 4, fixed: 2, when: '5h ago' },
  { id: 'e5', target: 'admin.acme.io', mode: 'advanced', status: 'delivered', grade: 'B', sev: { c: 0, h: 1, m: 3, l: 2 }, open: 4, fixed: 2, when: 'Jun 2' },
  { id: 'e6', target: 'vpn.acme.io', mode: 'advanced', status: 'waiting', grade: 'D', sev: { c: 2, h: 1, m: 1, l: 1 }, open: 3, fixed: 2, when: '1d ago' },
  { id: 'e7', target: 'cdn.acme.io', mode: 'standard', status: 'scanning', grade: 'B', sev: { c: 0, h: 2, m: 2, l: 3 }, open: 5, fixed: 2, when: '20m ago' },
  { id: 'e8', target: 'mail.acme.io', mode: 'standard', status: 'delivered', grade: 'A', sev: { c: 1, h: 0, m: 1, l: 2 }, open: 2, fixed: 2, when: 'May 22' },
]

// Aggregate posture derived across all engagements, so the cockpit and Findings agree.
const _sev = (k: 'c' | 'h' | 'm' | 'l') => engagements.reduce((a, e) => a + e.sev[k], 0)
const _open = engagements.reduce((a, e) => a + e.open, 0)
const _fixed = engagements.reduce((a, e) => a + e.fixed, 0)
const _total = _sev('c') + _sev('h') + _sev('m') + _sev('l')
export const posture = {
  critical: _sev('c'), high: _sev('h'), medium: _sev('m'), low: _sev('l'),
  open: _open, total: _total, fixed: _fixed, resolved: Math.round((_fixed / _total) * 100),
}

// Open findings by severity over 6 months (stacked trend). Last month sums to posture.open.
export const trend = [
  { month: 'Feb', critical: 9, high: 15, medium: 19, low: 15 },
  { month: 'Mar', critical: 8, high: 13, medium: 18, low: 14 },
  { month: 'Apr', critical: 7, high: 12, medium: 16, low: 13 },
  { month: 'May', critical: 6, high: 11, medium: 15, low: 12 },
  { month: 'Jun', critical: 6, high: 10, medium: 14, low: 12 },
  { month: 'Jul', critical: 6, high: 9, medium: 6, low: 5 },
]

export const latestReport = {
  engagement: 'acme.io, Standard VA', delivered: 'Jun 18, 2026', templates: 4, findings: 39, signed: true,
}

export const cockpit = { me, engagements, posture, trend, latestReport }

// Client's tasks (mock VITE_MOCK=1), in the API's client vocabulary.
const win = (from: string, to: string) => ({ not_before: from, not_after: to })
export const tasks = [
  { id: 't1', target: 'https://portal.samudera.co.id', path: '/app', port: null, notes: 'Akun uji: demo/demo', scan_mode: 'cloud', status: 'in_review', when: '2h ago', reason: null, job_id: null, scheduled_at: null, ...win('2026-10-08T01:00:00Z', '2026-10-12T10:00:00Z') },
  { id: 't2', target: 'https://tracking.samudera.co.id', path: '', port: 8443, notes: '', scan_mode: 'cloud', status: 'scheduled', when: '20m ago', reason: null, job_id: null, scheduled_at: '2026-10-09T02:00:00Z', ...win('2026-10-08T01:00:00Z', '2026-10-10T10:00:00Z') },
  { id: 't3', target: 'http://10.0.4.12', path: '', port: null, notes: 'Server internal gudang', scan_mode: 'local', status: 'waiting', when: '5m ago', reason: null, job_id: null, scheduled_at: null, ...win('2026-10-09T01:00:00Z', '2026-10-15T10:00:00Z') },
  { id: 't4', target: 'https://app.samudera.co.id', path: '', port: null, notes: '', scan_mode: 'cloud', status: 'delivered', when: 'Sep 30', reason: null, job_id: null, scheduled_at: null, ...win('2026-09-20T01:00:00Z', '2026-09-30T10:00:00Z') },
  { id: 't5', target: 'https://legacy.samudera.co.id', path: '', port: null, notes: '', scan_mode: 'cloud', status: 'declined', when: '3d ago', reason: 'Bukti kepemilikan domain belum kami terima. Mohon kirim ulang dengan surat kuasa.', job_id: null, scheduled_at: null, ...win('2026-10-01T01:00:00Z', '2026-10-05T10:00:00Z') },
]

// Client's delivered reports (download + view-once password).
export const reports = [
  { id: 'rep1', engagement: 'acme.io, Standard VA', delivered: 'Jun 18, 2026', findings: 39, templates: ['Formal handover', 'Full technical', 'Executive summary', 'Raw (FP/TP)'], signed: true },
  { id: 'rep2', engagement: 'admin.acme.io, Advanced VA', delivered: 'Jun 2, 2026', findings: 6, templates: ['Formal handover', 'Full technical', 'Executive summary'], signed: true },
  { id: 'rep3', engagement: 'mail.acme.io, Standard VA', delivered: 'May 22, 2026', findings: 4, templates: ['Formal handover', 'Executive summary'], signed: true },
  { id: 'rep4', engagement: 'shop.acme.io, Standard VA', delivered: 'May 30, 2026', findings: 12, templates: ['Formal handover', 'Executive summary'], signed: true },
  { id: 'rep5', engagement: 'status.acme.io, Standard VA', delivered: 'May 8, 2026', findings: 3, templates: ['Formal handover', 'Executive summary'], signed: true },
  { id: 'rep6', engagement: 'docs.acme.io, Standard VA', delivered: 'Apr 30, 2026', findings: 5, templates: ['Formal handover', 'Executive summary', 'Raw (FP/TP)'], signed: true },
]

// --- Team side (mock): the role-scoped task board ---
const act = (to: string, kind: string, comment = false) => ({ to, kind, comment, allowed: true, why: null })
const card = (id: string, stage: string, scanState: string | null, client: string, target: string, meta: string, actions: any[], extra: object = {}) => ({
  id, version: 1, stage, scanState, client, target, scanMode: 'cloud', sev: { c: 0, h: 1, m: 2, l: 1 }, meta,
  assignee: stage === 'task' ? null : 'dimas', jobId: null, suspended: scanState === 'suspended', reason: null, actions, ...extra,
})
export const taskBoard = [
  { id: 'task', title: 'Tasks', accent: 'accent', cards: [card('k1', 'task', null, 'PT Samudera Logistik', 'http://10.0.4.12', 'Submitted 5m ago', [act('scan/pending', 'claim'), act('declined', 'decline', true)])] },
  { id: 'scan', title: 'Scans', accent: 'info', cards: [
    card('k2', 'scan', 'scheduled', 'PT Samudera Logistik', 'https://tracking.samudera.co.id:8443', 'Starts 2026-10-09T02:00:00+00:00', [act('scan/pending', 'unschedule')]),
    card('k3', 'scan', 'suspended', 'PT Nusantara Pelabuhan', 'https://kapal.nusantara.co.id', 'agent offline', [act('scan/in_progress', 'resume'), act('scan/scheduled', 'schedule'), act('expired', 'close', true)]),
  ] },
  { id: 'completed', title: 'Completed', accent: 'high', cards: [card('t1', 'completed', null, 'PT Samudera Logistik', 'https://portal.samudera.co.id', 'Scan finished, ready to audit', [act('review_lead_pentester', 'submit')])] },
  { id: 'review_lead_pentester', title: 'Lead Pentester review', accent: 'crit', cards: [card('k5', 'review_lead_pentester', null, 'PT Samudera Logistik', 'https://portal.samudera.co.id/app', 'v2 · riyan', [act('review_lead_cyber', 'approve'), act('completed', 'send_back', true)])] },
  { id: 'review_lead_cyber', title: 'Lead Cyber review', accent: 'med', cards: [] },
  { id: 'review_governance', title: 'Governance review', accent: 'med', cards: [] },
  { id: 'review_manager', title: 'Manager review', accent: 'high', cards: [] },
  { id: 'delivered', title: 'Delivered', accent: 'low', cards: [card('k6', 'delivered', null, 'PT Samudera Logistik', 'https://app.samudera.co.id', '2026-09-30 · PDF sent', [])] },
  { id: 'closed', title: 'Declined / Expired', accent: 'crit', cards: [card('k7', 'declined', null, 'PT Samudera Logistik', 'https://legacy.samudera.co.id', 'Bukti kepemilikan domain belum kami terima', [])] },
]

export const taskDetail = (id: string) => ({
  task: { id, target: 'https://portal.samudera.co.id', path: '/app', port: null, notes: 'Akun uji: demo/demo', scan_mode: 'cloud',
    not_before: '2026-10-08T01:00:00Z', not_after: '2026-10-12T10:00:00Z', max_minutes: 240, scheduled_at: null,
    assignee: 'dimas', suspend_reason: null, decline_cause: null, stage: 'review_lead_pentester', scan_state: null, version: 1, job_id: null },
  can_audit: true, has_report: true,
})

// System administrator console (VITE_MOCK=1): organizations and every account, Indonesian sample data.
export const orgs = [
  { id: 'org-garuda', name: 'CV Garuda Teknologi', status: 'disabled', created_at: '2026-08-02 10:15:00' },
  { id: 'org-nusantara', name: 'PT Nusantara Pelabuhan', status: 'active', created_at: '2026-07-21 08:30:00' },
  { id: 'org-samudera', name: 'PT Samudera Logistik', status: 'active', created_at: '2026-07-14 09:00:00' },
  { id: 'org-sinar', name: 'PT Sinar Cargo Indonesia', status: 'active', created_at: '2026-09-03 13:45:00' },
]

export const accounts = [
  { username: 'sysadmin', role: 'sysadmin', org_id: null, display_name: 'Bambang Sutrisno', email: 'bambang@varuna.co.id', disabled: 0, totp_enabled: 1, must_change_password: 0, created_at: '2026-07-01 08:00:00' },
  { username: 'riyan', role: 'lead_pentester', org_id: null, display_name: 'Riyan Pratama', email: 'riyan@varuna.co.id', disabled: 0, totp_enabled: 1, must_change_password: 0, created_at: '2026-07-01 08:10:00' },
  { username: 'dimas', role: 'pentester', org_id: null, display_name: 'Dimas Saputra', email: 'dimas@varuna.co.id', disabled: 0, totp_enabled: 1, must_change_password: 0, created_at: '2026-07-02 09:00:00' },
  { username: 'aisah', role: 'lead_cyber', org_id: null, display_name: 'Aisah Rahmawati', email: 'aisah@varuna.co.id', disabled: 0, totp_enabled: 1, must_change_password: 0, created_at: '2026-07-02 09:20:00' },
  { username: 'hani', role: 'governance', org_id: null, display_name: 'Hani Lestari', email: 'hani@varuna.co.id', disabled: 0, totp_enabled: 0, must_change_password: 1, created_at: '2026-07-03 10:00:00' },
  { username: 'bayu', role: 'manager', org_id: null, display_name: 'Bayu Wicaksono', email: 'bayu@varuna.co.id', disabled: 0, totp_enabled: 0, must_change_password: 0, created_at: '2026-07-03 10:30:00' },
  { username: 'samudera', role: 'client', org_id: 'org-samudera', display_name: 'Siti Nurhaliza', email: 'it@samudera.co.id', disabled: 0, totp_enabled: 0, must_change_password: 0, created_at: '2026-07-14 09:05:00' },
  { username: 'nusantara.it', role: 'client', org_id: 'org-nusantara', display_name: 'Agus Hidayat', email: 'agus@nusantarapelabuhan.co.id', disabled: 0, totp_enabled: 0, must_change_password: 1, created_at: '2026-07-21 08:40:00' },
  { username: 'garuda', role: 'client', org_id: 'org-garuda', display_name: 'Dewi Kartika', email: 'dewi@garudatek.co.id', disabled: 1, totp_enabled: 0, must_change_password: 0, created_at: '2026-08-02 10:20:00' },
  { username: 'sinar.cargo', role: 'client', org_id: 'org-sinar', display_name: 'Rudi Hartono', email: 'rudi@sinarcargo.co.id', disabled: 0, totp_enabled: 0, must_change_password: 0, created_at: '2026-09-03 14:00:00' },
] as {
  username: string; role: string; org_id: string | null; display_name: string | null; email: string | null
  disabled: number; totp_enabled: number; must_change_password: number; created_at: string
}[]
