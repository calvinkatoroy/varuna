// Placeholder data for the mock-first prototype. Shapes mirror the real API where an endpoint
// exists; the client-posture aggregates (posture/trend/assets) are prototype-only until the
// backend client-findings aggregation lands (documented follow-up).

export const me = { username: 'acme', role: 'client' }

export const engagements = [
  { id: 'e1', target: 'api.acme.io — Full VA', detail: 'Advanced · nuclei + sqlmap', when: '2h ago', status: 'in_review' },
  { id: 'e2', target: 'acme.io — Standard VA', detail: 'Delivered · 4 templates', when: 'Jun 18', status: 'delivered' },
  { id: 'e3', target: 'staging.acme.io', detail: 'Katana → Nuclei running', when: 'now', status: 'scanning' },
]

export const posture = { critical: 2, high: 5, medium: 11, low: 8, open: 18, total: 42, fixed: 24, hygiene: 72 }

export const trend = [
  { month: 'Jan', open: 44 }, { month: 'Feb', open: 41 }, { month: 'Mar', open: 33 },
  { month: 'Apr', open: 28 }, { month: 'May', open: 22 }, { month: 'Jun', open: 18 },
]

export const assets = [
  { host: 'api.acme.io', grade: 'D', label: 'Poor', open: 7 },
  { host: 'acme.io', grade: 'A', label: 'Good', open: 1 },
  { host: 'staging.acme.io', grade: 'C', label: 'Fair', open: 6 },
  { host: 'admin.acme.io', grade: 'B', label: 'Fair', open: 4 },
]

export const latestReport = {
  engagement: 'acme.io — Standard VA', delivered: 'Jun 18, 2026', templates: 4, findings: 27, signed: true,
}

export const team = [
  { name: 'Riyan', role: 'Lead pentester', status: 'Approved' },
  { name: 'Aisah', role: 'Reporter', status: 'Reviewed' },
  { name: 'Hani', role: 'Governance', status: 'In review' },
]

// Convenience aggregate the cockpit reads in mock mode.
export const cockpit = { me, engagements, posture, trend, assets, latestReport, team }

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
  { id: 'f4', name: 'Verbose error message', severity: 'low', asset: '/api/v1/orders', tool: 'nuclei', cve: 'CWE-209', verdict: 'fp', status: 'open', evidence: 'Stack trace on 500 — turned out to be a staging-only debug flag', remediation: 'Suppress stack traces in production; return generic error responses.' },
  { id: 'f5', name: 'Outdated jQuery 1.12.4', severity: 'medium', asset: '/static/js/vendor.js', tool: 'nuclei', cve: 'CVE-2020-11022', verdict: 'tp', status: 'open', evidence: 'jQuery 1.12.4 fingerprinted — known XSS in .html()', remediation: 'Upgrade to a supported jQuery release and re-test dependent widgets.' },
  { id: 'f6', name: 'Directory listing enabled', severity: 'low', asset: '/uploads/', tool: 'katana', cve: 'CWE-548', verdict: 'tp', status: 'open', evidence: 'Autoindex exposes uploaded files', remediation: 'Disable directory autoindexing; place an index file or deny listing at the web-server config.' },
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

