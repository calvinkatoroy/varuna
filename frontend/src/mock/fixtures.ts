// Placeholder data for the mock-first prototype. Shapes mirror the real API where an endpoint
// exists; the client-posture aggregates (posture/trend/assets) are prototype-only until the
// backend client-findings aggregation lands (documented follow-up).

export const me = { username: 'acme', name: 'Acme Corp', role: 'client' }

// Engagements are the core entity of the portfolio cockpit. Each absorbs its target "asset":
// grade, severity breakdown, open/fixed counts, status. Click one to drill into its findings.
export const engagements = [
  { id: 'e1', target: 'api.acme.io', mode: 'advanced', status: 'in_review', grade: 'D', sev: { c: 1, h: 2, m: 1, l: 0 }, open: 4, fixed: 0, when: '2h ago' },
  { id: 'e2', target: 'acme.io', mode: 'standard', status: 'delivered', grade: 'A', sev: { c: 0, h: 0, m: 1, l: 1 }, open: 1, fixed: 1, when: 'Jun 18' },
  { id: 'e3', target: 'staging.acme.io', mode: 'standard', status: 'scanning', grade: 'C', sev: { c: 1, h: 1, m: 2, l: 1 }, open: 3, fixed: 2, when: 'now' },
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

// Open findings by severity over 6 months (stacked trend). Last month sums to posture.open (8).
export const trend = [
  { month: 'Feb', critical: 3, high: 6, medium: 6, low: 4 },
  { month: 'Mar', critical: 3, high: 5, medium: 5, low: 3 },
  { month: 'Apr', critical: 2, high: 4, medium: 5, low: 2 },
  { month: 'May', critical: 2, high: 3, medium: 4, low: 2 },
  { month: 'Jun', critical: 1, high: 2, medium: 4, low: 2 },
  { month: 'Jul', critical: 1, high: 2, medium: 3, low: 2 },
]

export const latestReport = {
  engagement: 'acme.io, Standard VA', delivered: 'Jun 18, 2026', templates: 4, findings: 27, signed: true,
}

export const cockpit = { me, engagements, posture, trend, latestReport }

// Client's scan proposals (distinct from the cockpit's engagements list).
export const proposals = [
  { id: 'pr1', target: 'api.acme.io', purpose: 'Pre-release', division: 'Engineering', status: 'in_review', when: '2h ago' },
  { id: 'pr2', target: 'acme.io', purpose: 'Compliance', division: 'IT', status: 'delivered', when: 'Jun 18' },
  { id: 'pr3', target: 'staging.acme.io', purpose: 'Periodic', division: 'Platform', status: 'scanning', when: 'now' },
  { id: 'pr4', target: 'shop.acme.io', purpose: 'Pre-release', division: 'E-commerce', status: 'pending', when: '12m ago' },
  { id: 'pr5', target: 'vpn.acme.io', purpose: 'Incident', division: 'SecOps', status: 'pending', when: '1d ago' },
]

// Client's delivered reports (download + view-once password).
export const reports = [
  { id: 'rep1', engagement: 'acme.io, Standard VA', delivered: 'Jun 18, 2026', findings: 27, templates: ['Formal handover', 'Full technical', 'Executive summary', 'Raw (FP/TP)'], signed: true },
  { id: 'rep2', engagement: 'shop.acme.io, Standard VA', delivered: 'May 30, 2026', findings: 12, templates: ['Formal handover', 'Executive summary'], signed: true },
]

// --- Team / advanced side: the review pipeline board (team sees ALL clients) ---
type Card = {
  id: string; client: string; target: string; mode: 'standard' | 'advanced'
  sev: { c: number; h: number; m: number; l: number }; meta: string; owner?: string
}
export const board: { id: string; title: string; accent: string; cards: Card[] }[] = [
  {
    id: 'pending', title: 'Pending approval', accent: 'accent',
    cards: [
      { id: 'p1', client: 'Acme Corp', target: 'api.acme.io', mode: 'advanced', sev: { c: 0, h: 0, m: 0, l: 0 }, meta: 'Submitted 12m ago' },
      { id: 'p2', client: 'Nimbus Ltd', target: 'nimbus.co/app', mode: 'standard', sev: { c: 0, h: 0, m: 0, l: 0 }, meta: 'Submitted 2h ago' },
    ],
  },
  {
    id: 'scanning', title: 'Scanning', accent: 'info',
    cards: [
      { id: 's1', client: 'Vault Bank', target: 'vaultbank.id', mode: 'standard', sev: { c: 0, h: 1, m: 3, l: 2 }, meta: 'Nuclei · 62%' },
    ],
  },
  {
    id: 'in_review_reporter', title: 'Reporter', accent: 'high',
    cards: [
      { id: 'r1', client: 'Acme Corp', target: 'acme.io', mode: 'standard', sev: { c: 2, h: 5, m: 11, l: 8 }, meta: 'v2 · editing', owner: 'Aisah' },
    ],
  },
  {
    id: 'in_review_lead', title: 'Lead', accent: 'crit',
    cards: [
      { id: 'l1', client: 'Shopwave', target: 'shopwave.store', mode: 'advanced', sev: { c: 1, h: 3, m: 6, l: 4 }, meta: 'v3 · reviewing', owner: 'Riyan' },
    ],
  },
  {
    id: 'in_review_governance', title: 'Governance', accent: 'med',
    cards: [
      { id: 'g1', client: 'Meridian Health', target: 'portal.meridian.health', mode: 'standard', sev: { c: 0, h: 2, m: 4, l: 9 }, meta: 'v4 · sign-off', owner: 'Hani' },
    ],
  },
  {
    id: 'delivered', title: 'Delivered', accent: 'low',
    cards: [
      { id: 'd1', client: 'Acme Corp', target: 'acme.io', mode: 'standard', sev: { c: 0, h: 2, m: 4, l: 8 }, meta: 'Jun 18 · PDF sent' },
      { id: 'd2', client: 'Orbit Media', target: 'orbit.media', mode: 'advanced', sev: { c: 0, h: 0, m: 2, l: 3 }, meta: 'Jun 14 · PDF sent' },
    ],
  },
]

// Findings master-detail (team review of a scanned engagement).
export const findings = [
  { id: 'f1', name: 'SQL Injection', severity: 'critical', asset: '/rest/products/search', tool: 'sqlmap', cve: 'CWE-89', verdict: 'tp', status: 'open', evidence: "q=1' AND SLEEP(5)-- -  →  10.0s response", remediation: 'Parameterize the query / use prepared statements. Validate and sanitize all user input; apply least-privilege DB accounts.' },
  { id: 'f2', name: 'Reflected XSS', severity: 'high', asset: '/search?q=', tool: 'nuclei', cve: 'CWE-79', verdict: 'tp', status: 'open', evidence: '<script>alert(1)</script> reflected unescaped in response body', remediation: 'Context-encode output, set a strict Content-Security-Policy, and use an auto-escaping template engine.' },
  { id: 'f3', name: 'Missing HSTS header', severity: 'medium', asset: 'api.acme.io', tool: 'nuclei', cve: 'CWE-319', verdict: 'tp', status: 'fixed', evidence: 'No Strict-Transport-Security header on HTTPS responses', remediation: 'Add Strict-Transport-Security: max-age=31536000; includeSubDomains.' },
  { id: 'f4', name: 'Verbose error message', severity: 'low', asset: '/api/v1/orders', tool: 'nuclei', cve: 'CWE-209', verdict: 'fp', status: 'open', evidence: 'Stack trace on 500, turned out to be a staging-only debug flag', remediation: 'Suppress stack traces in production; return generic error responses.' },
  { id: 'f5', name: 'Outdated jQuery 1.12.4', severity: 'medium', asset: '/static/js/vendor.js', tool: 'nuclei', cve: 'CVE-2020-11022', verdict: 'tp', status: 'open', evidence: 'jQuery 1.12.4 fingerprinted, known XSS in .html()', remediation: 'Upgrade to a supported jQuery release and re-test dependent widgets.' },
  { id: 'f6', name: 'Directory listing enabled', severity: 'low', asset: '/uploads/', tool: 'katana', cve: 'CWE-548', verdict: 'tp', status: 'open', evidence: 'Autoindex exposes uploaded files', remediation: 'Disable directory autoindexing; place an index file or deny listing at the web-server config.' },
  { id: 'f7', name: 'Broken access control', severity: 'critical', asset: '/api/v1/admin/users', tool: 'nuclei', cve: 'CWE-284', verdict: 'tp', status: 'open', evidence: 'IDOR: user token reaches /admin/users and returns all records', remediation: 'Enforce server-side authorization on every object reference; deny by default and scope queries to the authenticated tenant.' },
  { id: 'f8', name: 'Weak TLS ciphers', severity: 'high', asset: 'api.acme.io:443', tool: 'nuclei', cve: 'CWE-327', verdict: 'tp', status: 'fixed', evidence: 'TLS 1.0 + RC4 negotiated on the edge listener', remediation: 'Disable TLS < 1.2 and legacy ciphers; prefer AEAD suites (AES-GCM, ChaCha20).' },
  { id: 'f9', name: 'CSRF token missing', severity: 'high', asset: '/account/email', tool: 'nuclei', cve: 'CWE-352', verdict: 'tp', status: 'open', evidence: 'State-changing POST accepted without an anti-CSRF token', remediation: 'Add per-session anti-CSRF tokens (or SameSite=strict cookies) and validate them on every state-changing request.' },
  { id: 'f10', name: 'Clickjacking', severity: 'medium', asset: 'acme.io', tool: 'nuclei', cve: 'CWE-1021', verdict: 'tp', status: 'open', evidence: 'Page framable, no X-Frame-Options / frame-ancestors', remediation: 'Set Content-Security-Policy: frame-ancestors none (or a strict allowlist).' },
  { id: 'f11', name: 'Cookie without Secure flag', severity: 'low', asset: 'acme.io', tool: 'nuclei', cve: 'CWE-614', verdict: 'tp', status: 'fixed', evidence: 'Session cookie set without Secure over HTTPS', remediation: 'Set Secure and HttpOnly on all session cookies; scope with SameSite.' },
  { id: 'f12', name: 'Open redirect', severity: 'medium', asset: '/login?next=', tool: 'katana', cve: 'CWE-601', verdict: 'tp', status: 'open', evidence: 'next= parameter redirects to arbitrary external host', remediation: 'Validate redirect targets against a server-side allowlist; never redirect to raw user input.' },
]

// Per-engagement detail for the review drawer.
export const engagementDetail = {
  r1: {
    client: 'Acme Corp', target: 'acme.io', mode: 'standard', stage: 'in_review_reporter',
    proposal: { purpose: 'Pre-release', division: 'Engineering', environment: 'Production', authorized: true },
    versions: [
      { n: 1, editor: 'system', note: 'auto-generated v1', when: 'Jun 19, 09:12' },
      { n: 2, editor: 'Aisah', note: 'fixed exec summary, marked 2 FPs', when: 'Jun 19, 14:40' },
    ],
  },
}

