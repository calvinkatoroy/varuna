// Placeholder data for the mock-first prototype. Shapes mirror the real API where an endpoint
// exists; the client-posture aggregates (posture/trend) are prototype-only until the backend
// client-findings aggregation lands (documented follow-up). Deliberately over-stuffed with rows
// so every page reads like a busy, real workspace rather than a 2-item demo.

export const me = { username: 'acme', name: 'Acme Corp', role: 'client' }

// Engagements are the core entity of the portfolio cockpit. Each absorbs its target "asset":
// grade, severity breakdown, open/fixed counts, status. Click one to drill into its findings.
export const engagements = [
  { id: 'e1', target: 'api.acme.io', mode: 'advanced', status: 'in_review', grade: 'D', sev: { c: 1, h: 2, m: 1, l: 0 }, open: 4, fixed: 0, when: '2h ago' },
  { id: 'e2', target: 'acme.io', mode: 'standard', status: 'delivered', grade: 'A', sev: { c: 0, h: 0, m: 1, l: 1 }, open: 1, fixed: 1, when: 'Jun 18' },
  { id: 'e3', target: 'staging.acme.io', mode: 'standard', status: 'scanning', grade: 'C', sev: { c: 1, h: 1, m: 2, l: 1 }, open: 3, fixed: 2, when: 'now' },
  { id: 'e4', target: 'shop.acme.io', mode: 'standard', status: 'in_review', grade: 'C', sev: { c: 1, h: 2, m: 2, l: 1 }, open: 4, fixed: 2, when: '5h ago' },
  { id: 'e5', target: 'admin.acme.io', mode: 'advanced', status: 'delivered', grade: 'B', sev: { c: 0, h: 1, m: 3, l: 2 }, open: 4, fixed: 2, when: 'Jun 2' },
  { id: 'e6', target: 'vpn.acme.io', mode: 'advanced', status: 'pending', grade: 'D', sev: { c: 2, h: 1, m: 1, l: 1 }, open: 3, fixed: 2, when: '1d ago' },
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

// Client's scan proposals (distinct from the cockpit's engagements list).
export const proposals = [
  { id: 'pr1', target: 'api.acme.io', purpose: 'Pre-release', division: 'Engineering', status: 'in_review', when: '2h ago' },
  { id: 'pr2', target: 'acme.io', purpose: 'Compliance', division: 'IT', status: 'delivered', when: 'Jun 18' },
  { id: 'pr3', target: 'staging.acme.io', purpose: 'Periodic', division: 'Platform', status: 'scanning', when: 'now' },
  { id: 'pr4', target: 'shop.acme.io', purpose: 'Pre-release', division: 'E-commerce', status: 'in_review', when: '5h ago' },
  { id: 'pr5', target: 'admin.acme.io', purpose: 'Compliance', division: 'IT', status: 'delivered', when: 'Jun 2' },
  { id: 'pr6', target: 'vpn.acme.io', purpose: 'Incident', division: 'SecOps', status: 'pending', when: '1d ago' },
  { id: 'pr7', target: 'cdn.acme.io', purpose: 'Periodic', division: 'Platform', status: 'scanning', when: '20m ago' },
  { id: 'pr8', target: 'mail.acme.io', purpose: 'Compliance', division: 'IT', status: 'delivered', when: 'May 22' },
  { id: 'pr9', target: 'partners.acme.io', purpose: 'Pre-release', division: 'Business Dev', status: 'pending', when: '2d ago' },
  { id: 'pr10', target: 'checkout.acme.io', purpose: 'Incident', division: 'E-commerce', status: 'pending', when: '3d ago' },
  { id: 'pr11', target: 'status.acme.io', purpose: 'Periodic', division: 'Platform', status: 'delivered', when: 'May 8' },
  { id: 'pr12', target: 'docs.acme.io', purpose: 'Pre-release', division: 'Developer Relations', status: 'delivered', when: 'Apr 30' },
  { id: 'pr13', target: 'legacy-vpn.acme.io', purpose: 'Incident', division: 'SecOps', status: 'rejected', when: '4d ago', reason: 'Authorization could not be verified: the submitting account is not listed as a technical or legal contact for this domain. Resubmit with proof of ownership or an authorization letter.' },
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

// --- Team / advanced side: the review pipeline board (team sees ALL clients) ---
type Card = {
  id: string; client: string; target: string; mode: 'standard' | 'advanced'
  sev: { c: number; h: number; m: number; l: number }; meta: string; owner?: string
  suspended?: boolean; rejectReason?: string
}
export const board: { id: string; title: string; accent: string; cards: Card[] }[] = [
  {
    id: 'pending', title: 'Pending approval', accent: 'accent',
    cards: [
      { id: 'p1', client: 'Acme Corp', target: 'partners.acme.io', mode: 'standard', sev: { c: 0, h: 0, m: 0, l: 0 }, meta: 'Submitted 12m ago' },
      { id: 'p2', client: 'Nimbus Ltd', target: 'nimbus.co/app', mode: 'standard', sev: { c: 0, h: 0, m: 0, l: 0 }, meta: 'Submitted 2h ago' },
      { id: 'p3', client: 'Acme Corp', target: 'vpn.acme.io', mode: 'advanced', sev: { c: 0, h: 0, m: 0, l: 0 }, meta: 'Submitted 1d ago' },
      { id: 'p4', client: 'Fernway Logistics', target: 'track.fernway.com', mode: 'standard', sev: { c: 0, h: 0, m: 0, l: 0 }, meta: 'Submitted 3h ago' },
      { id: 'p5', client: 'Brightside Retail', target: 'checkout.brightside.io', mode: 'standard', sev: { c: 0, h: 0, m: 0, l: 0 }, meta: 'Submitted 40m ago' },
    ],
  },
  {
    id: 'scanning', title: 'Scanning', accent: 'info',
    cards: [
      { id: 's1', client: 'Vault Bank', target: 'vaultbank.id', mode: 'standard', sev: { c: 0, h: 1, m: 3, l: 2 }, meta: 'Nuclei · 62%' },
      { id: 's2', client: 'Acme Corp', target: 'staging.acme.io', mode: 'standard', sev: { c: 1, h: 1, m: 2, l: 1 }, meta: 'Katana → Nuclei · 41%' },
      { id: 's3', client: 'Acme Corp', target: 'cdn.acme.io', mode: 'standard', sev: { c: 0, h: 2, m: 2, l: 3 }, meta: 'Nuclei · 78%' },
      { id: 's4', client: 'Lumen Health', target: 'portal.lumenhealth.io', mode: 'advanced', sev: { c: 0, h: 0, m: 1, l: 1 }, meta: 'SQLMap queued' },
    ],
  },
  {
    id: 'in_review_reporter', title: 'Reporter', accent: 'high',
    cards: [
      { id: 'r1', client: 'Acme Corp', target: 'acme.io', mode: 'standard', sev: { c: 2, h: 5, m: 11, l: 8 }, meta: 'v2 · editing', owner: 'Aisah' },
      { id: 'r2', client: 'Acme Corp', target: 'api.acme.io', mode: 'advanced', sev: { c: 1, h: 2, m: 1, l: 0 }, meta: 'v1 · drafting', owner: 'Aisah' },
      { id: 'r3', client: 'Northwind Freight', target: 'app.northwindfreight.com', mode: 'standard', sev: { c: 0, h: 1, m: 3, l: 4 }, meta: 'v1 · editing', owner: 'Aisah' },
    ],
  },
  {
    id: 'in_review_lead', title: 'Lead', accent: 'crit',
    cards: [
      { id: 'l1', client: 'Shopwave', target: 'shopwave.store', mode: 'advanced', sev: { c: 1, h: 3, m: 6, l: 4 }, meta: 'v3 · reviewing', owner: 'Riyan' },
      { id: 'l2', client: 'Acme Corp', target: 'shop.acme.io', mode: 'standard', sev: { c: 1, h: 2, m: 2, l: 1 }, meta: 'v2 · reviewing', owner: 'Riyan' },
    ],
  },
  {
    id: 'in_review_governance', title: 'Governance', accent: 'med',
    cards: [
      { id: 'g1', client: 'Meridian Health', target: 'portal.meridian.health', mode: 'standard', sev: { c: 0, h: 2, m: 4, l: 9 }, meta: 'v4 · sign-off', owner: 'Hani' },
      { id: 'g2', client: 'Acme Corp', target: 'admin.acme.io', mode: 'advanced', sev: { c: 0, h: 1, m: 3, l: 2 }, meta: 'v3 · sign-off', owner: 'Hani' },
    ],
  },
  {
    id: 'delivered', title: 'Delivered', accent: 'low',
    cards: [
      { id: 'd1', client: 'Acme Corp', target: 'acme.io', mode: 'standard', sev: { c: 0, h: 2, m: 4, l: 8 }, meta: 'Jun 18 · PDF sent' },
      { id: 'd2', client: 'Orbit Media', target: 'orbit.media', mode: 'advanced', sev: { c: 0, h: 0, m: 2, l: 3 }, meta: 'Jun 14 · PDF sent' },
      { id: 'd3', client: 'Acme Corp', target: 'mail.acme.io', mode: 'standard', sev: { c: 1, h: 0, m: 1, l: 2 }, meta: 'May 22 · PDF sent' },
      { id: 'd4', client: 'Acme Corp', target: 'status.acme.io', mode: 'standard', sev: { c: 0, h: 0, m: 1, l: 2 }, meta: 'May 8 · PDF sent' },
      { id: 'd5', client: 'Acme Corp', target: 'docs.acme.io', mode: 'standard', sev: { c: 0, h: 1, m: 2, l: 2 }, meta: 'Apr 30 · PDF sent' },
      { id: 'd6', client: 'Calder Insurance', target: 'quote.calderinsurance.com', mode: 'standard', sev: { c: 0, h: 0, m: 2, l: 4 }, meta: 'Apr 25 · PDF sent' },
    ],
  },
  {
    // Terminal, off the pending->...->delivered stepper. Proposals land here (with a reason)
    // instead of being deleted, so rejection has an audit trail on the team side too.
    id: 'rejected', title: 'Rejected', accent: 'crit',
    cards: [
      { id: 'x1', client: 'Meridian Health', target: 'legacy-vpn.meridian.health', mode: 'standard', sev: { c: 0, h: 0, m: 0, l: 0 }, meta: 'Authorization could not be verified', rejectReason: 'Authorization could not be verified: submitter is not listed as a technical or legal contact for this domain.' },
    ],
  },
]

// Findings master-detail (team review + client-facing confirmed list). Sums to posture:
// 6 critical, 9 high, 13 medium, 11 low (39 confirmed, 26 open, 13 fixed) plus a handful of
// false positives the team already triaged out (kept here for the Team Findings review page).
export const findings = [
  // Critical (6)
  { id: 'f1', name: 'SQL Injection', severity: 'critical', asset: '/rest/products/search', tool: 'sqlmap', cve: 'CWE-89', verdict: 'tp', status: 'open', evidence: "q=1' AND SLEEP(5)-- -  →  10.0s response", remediation: 'Parameterize the query / use prepared statements. Validate and sanitize all user input; apply least-privilege DB accounts.' },
  { id: 'f2', name: 'Broken access control', severity: 'critical', asset: '/api/v1/admin/users', tool: 'nuclei', cve: 'CWE-284', verdict: 'tp', status: 'open', evidence: 'IDOR: user token reaches /admin/users and returns all records', remediation: 'Enforce server-side authorization on every object reference; deny by default and scope queries to the authenticated tenant.' },
  { id: 'f3', name: 'SQL Injection (login form)', severity: 'critical', asset: '/auth/login', tool: 'sqlmap', cve: 'CWE-89', verdict: 'tp', status: 'fixed', evidence: "username=admin' OR '1'='1 bypasses authentication", remediation: 'Use parameterized queries for all auth paths; add a WAF rule as defense-in-depth.' },
  { id: 'f4', name: 'Unrestricted file upload (RCE)', severity: 'critical', asset: '/api/v1/uploads', tool: 'nuclei', cve: 'CWE-434', verdict: 'tp', status: 'open', evidence: 'A .php file uploaded to /uploads/ is served and executed by the web server', remediation: 'Validate file type by content (not extension), store uploads outside the webroot, and disable script execution in the upload directory.' },
  { id: 'f5', name: 'IDOR on invoice download', severity: 'critical', asset: '/api/v1/invoices/{id}', tool: 'nuclei', cve: 'CWE-639', verdict: 'tp', status: 'open', evidence: 'Incrementing {id} returns other tenants\' invoices without authorization checks', remediation: 'Verify the requesting tenant owns the resource before returning it; use non-sequential opaque identifiers.' },
  { id: 'f6', name: 'SSO authentication bypass', severity: 'critical', asset: '/sso/callback', tool: 'nuclei', cve: 'CWE-287', verdict: 'tp', status: 'fixed', evidence: 'SAML response signature not validated, forged assertions accepted', remediation: 'Validate the SAML response signature against the IdP\'s public certificate on every callback; reject unsigned assertions.' },

  // High (9)
  { id: 'f7', name: 'Reflected XSS', severity: 'high', asset: '/search?q=', tool: 'nuclei', cve: 'CWE-79', verdict: 'tp', status: 'open', evidence: '<script>alert(1)</script> reflected unescaped in response body', remediation: 'Context-encode output, set a strict Content-Security-Policy, and use an auto-escaping template engine.' },
  { id: 'f8', name: 'Weak TLS ciphers', severity: 'high', asset: 'api.acme.io:443', tool: 'nuclei', cve: 'CWE-327', verdict: 'tp', status: 'fixed', evidence: 'TLS 1.0 + RC4 negotiated on the edge listener', remediation: 'Disable TLS < 1.2 and legacy ciphers; prefer AEAD suites (AES-GCM, ChaCha20).' },
  { id: 'f9', name: 'CSRF token missing', severity: 'high', asset: '/account/email', tool: 'nuclei', cve: 'CWE-352', verdict: 'tp', status: 'open', evidence: 'State-changing POST accepted without an anti-CSRF token', remediation: 'Add per-session anti-CSRF tokens (or SameSite=strict cookies) and validate them on every state-changing request.' },
  { id: 'f10', name: 'Stored XSS in profile bio', severity: 'high', asset: '/api/v1/profile', tool: 'nuclei', cve: 'CWE-79', verdict: 'tp', status: 'open', evidence: 'Bio field renders raw HTML for every visitor of the profile page', remediation: 'Sanitize on write and encode on render; disallow script/style tags in user-generated content.' },
  { id: 'f11', name: 'Vertical privilege escalation', severity: 'high', asset: '/api/v1/roles', tool: 'nuclei', cve: 'CWE-269', verdict: 'tp', status: 'fixed', evidence: 'A standard-role token can PATCH its own role to admin', remediation: 'Role changes must require a privileged actor; validate the caller\'s own role server-side before any elevation.' },
  { id: 'f12', name: 'Server-Side Request Forgery', severity: 'high', asset: '/api/v1/fetch-preview', tool: 'nuclei', cve: 'CWE-918', verdict: 'tp', status: 'fixed', evidence: 'url= parameter reaches internal metadata endpoint (169.254.169.254)', remediation: 'Allowlist outbound destinations; block requests to link-local/internal ranges at the application layer.' },
  { id: 'f13', name: 'Insecure deserialization', severity: 'high', asset: '/api/v1/import', tool: 'nuclei', cve: 'CWE-502', verdict: 'tp', status: 'open', evidence: 'Untrusted serialized object accepted and deserialized without type checks', remediation: 'Avoid native deserialization of untrusted input; use a safe data format (JSON) with strict schema validation.' },
  { id: 'f14', name: 'XML External Entity (XXE)', severity: 'high', asset: '/api/v1/import-xml', tool: 'nuclei', cve: 'CWE-611', verdict: 'tp', status: 'open', evidence: 'DOCTYPE with external entity reference reads local /etc/passwd', remediation: 'Disable external entity resolution in the XML parser; prefer JSON where possible.' },
  { id: 'f15', name: 'JWT signature not verified', severity: 'high', asset: '/api/v1/session', tool: 'nuclei', cve: 'CWE-347', verdict: 'tp', status: 'open', evidence: 'alg=none token accepted, signature check silently skipped', remediation: 'Explicitly allowlist accepted algorithms server-side; never trust the alg header from the client.' },

  // Medium (13)
  { id: 'f16', name: 'Missing HSTS header', severity: 'medium', asset: 'api.acme.io', tool: 'nuclei', cve: 'CWE-319', verdict: 'tp', status: 'fixed', evidence: 'No Strict-Transport-Security header on HTTPS responses', remediation: 'Add Strict-Transport-Security: max-age=31536000; includeSubDomains.' },
  { id: 'f17', name: 'Missing HSTS header', severity: 'medium', asset: 'shop.acme.io', tool: 'nuclei', cve: 'CWE-319', verdict: 'tp', status: 'open', evidence: 'No Strict-Transport-Security header on HTTPS responses', remediation: 'Add Strict-Transport-Security: max-age=31536000; includeSubDomains.' },
  { id: 'f18', name: 'Outdated jQuery 1.12.4', severity: 'medium', asset: '/static/js/vendor.js', tool: 'nuclei', cve: 'CVE-2020-11022', verdict: 'tp', status: 'open', evidence: 'jQuery 1.12.4 fingerprinted, known XSS in .html()', remediation: 'Upgrade to a supported jQuery release and re-test dependent widgets.' },
  { id: 'f19', name: 'Clickjacking', severity: 'medium', asset: 'acme.io', tool: 'nuclei', cve: 'CWE-1021', verdict: 'tp', status: 'open', evidence: 'Page framable, no X-Frame-Options / frame-ancestors', remediation: 'Set Content-Security-Policy: frame-ancestors none (or a strict allowlist).' },
  { id: 'f20', name: 'Open redirect', severity: 'medium', asset: '/login?next=', tool: 'katana', cve: 'CWE-601', verdict: 'tp', status: 'open', evidence: 'next= parameter redirects to arbitrary external host', remediation: 'Validate redirect targets against a server-side allowlist; never redirect to raw user input.' },
  { id: 'f21', name: 'Missing rate limiting on login', severity: 'medium', asset: '/auth/login', tool: 'nuclei', cve: 'CWE-307', verdict: 'tp', status: 'open', evidence: '5,000 login attempts accepted from one IP in under a minute', remediation: 'Add exponential backoff / lockout after repeated failures, and rate-limit by IP and by account.' },
  { id: 'f22', name: 'Weak password policy', severity: 'medium', asset: '/account/password', tool: 'nuclei', cve: 'CWE-521', verdict: 'tp', status: 'fixed', evidence: 'Passwords as short as 4 characters accepted, no complexity check', remediation: 'Enforce a minimum length (12+) and check against a breached-password list (e.g. HIBP range API).' },
  { id: 'f23', name: 'Session fixation', severity: 'medium', asset: '/auth/login', tool: 'nuclei', cve: 'CWE-384', verdict: 'tp', status: 'open', evidence: 'Session ID issued pre-login is still valid after successful authentication', remediation: 'Rotate the session identifier immediately after a successful login.' },
  { id: 'f24', name: 'Cookie missing SameSite', severity: 'medium', asset: 'acme.io', tool: 'nuclei', cve: 'CWE-1275', verdict: 'tp', status: 'fixed', evidence: 'Session cookie has no SameSite attribute set', remediation: 'Set SameSite=Lax (or Strict where feasible) on all session cookies.' },
  { id: 'f25', name: 'Directory listing enabled', severity: 'medium', asset: '/backups/', tool: 'katana', cve: 'CWE-548', verdict: 'tp', status: 'fixed', evidence: 'Autoindex exposes a directory containing database backup files', remediation: 'Disable directory autoindexing; move backups outside the webroot entirely.' },
  { id: 'f26', name: 'Missing Content-Security-Policy', severity: 'medium', asset: 'shop.acme.io', tool: 'nuclei', cve: 'CWE-1021', verdict: 'tp', status: 'open', evidence: 'No CSP header present on any response', remediation: 'Ship a restrictive CSP (script-src self, no unsafe-inline) and iterate from report-only mode.' },
  { id: 'f27', name: 'Outdated TLS certificate warning', severity: 'medium', asset: 'admin.acme.io', tool: 'nuclei', cve: 'CWE-295', verdict: 'tp', status: 'open', evidence: 'Certificate expires in 6 days with no auto-renewal configured', remediation: 'Automate renewal (ACME/certbot) and alert on certificates expiring within 30 days.' },
  { id: 'f28', name: 'Verbose stack trace in production', severity: 'medium', asset: '/api/v1/orders', tool: 'nuclei', cve: 'CWE-209', verdict: 'tp', status: 'open', evidence: 'Unhandled exception returns a full stack trace including file paths', remediation: 'Return generic error responses in production; log full traces server-side only.' },

  // Low (11)
  { id: 'f29', name: 'Cookie without Secure flag', severity: 'low', asset: 'acme.io', tool: 'nuclei', cve: 'CWE-614', verdict: 'tp', status: 'fixed', evidence: 'Session cookie set without Secure over HTTPS', remediation: 'Set Secure and HttpOnly on all session cookies; scope with SameSite.' },
  { id: 'f30', name: 'Directory listing enabled', severity: 'low', asset: '/uploads/', tool: 'katana', cve: 'CWE-548', verdict: 'tp', status: 'open', evidence: 'Autoindex exposes uploaded files', remediation: 'Disable directory autoindexing; place an index file or deny listing at the web-server config.' },
  { id: 'f31', name: 'Missing X-Content-Type-Options', severity: 'low', asset: 'cdn.acme.io', tool: 'nuclei', cve: 'CWE-693', verdict: 'tp', status: 'open', evidence: 'No X-Content-Type-Options: nosniff header on static assets', remediation: 'Add X-Content-Type-Options: nosniff to every response.' },
  { id: 'f32', name: 'Password field allows autocomplete', severity: 'low', asset: '/auth/login', tool: 'nuclei', cve: 'CWE-522', verdict: 'tp', status: 'open', evidence: 'autocomplete attribute not disabled on the password input', remediation: 'Set autocomplete="new-password" (or off) on sensitive credential fields.' },
  { id: 'f33', name: 'Server banner discloses version', severity: 'low', asset: 'mail.acme.io', tool: 'nuclei', cve: 'CWE-200', verdict: 'tp', status: 'fixed', evidence: 'Server header returns nginx/1.18.0, aiding version fingerprinting', remediation: 'Suppress or generalize the Server header (e.g. server_tokens off in nginx).' },
  { id: 'f34', name: 'Missing SPF record', severity: 'low', asset: 'mail.acme.io', tool: 'nuclei', cve: 'CWE-290', verdict: 'tp', status: 'fixed', evidence: 'No SPF TXT record published for the sending domain', remediation: 'Publish an SPF record scoped to your actual mail-sending infrastructure.' },
  { id: 'f35', name: 'Outdated jQuery (low-risk path)', severity: 'low', asset: 'status.acme.io', tool: 'nuclei', cve: 'CVE-2020-11022', verdict: 'tp', status: 'open', evidence: 'jQuery 1.12.4 fingerprinted; no exploitable sink identified on this asset', remediation: 'Upgrade for defense-in-depth even though no current sink was reachable.' },
  { id: 'f36', name: 'Cacheable HTTPS response with session data', severity: 'low', asset: '/account/summary', tool: 'nuclei', cve: 'CWE-524', verdict: 'tp', status: 'open', evidence: 'Cache-Control missing on a response containing account details', remediation: 'Set Cache-Control: no-store on any response containing session-specific data.' },
  { id: 'f37', name: 'Missing Referrer-Policy', severity: 'low', asset: 'docs.acme.io', tool: 'nuclei', cve: 'CWE-200', verdict: 'tp', status: 'open', evidence: 'Full URL (with query params) leaks to third-party resources via the Referer header', remediation: 'Set Referrer-Policy: strict-origin-when-cross-origin.' },
  { id: 'f38', name: 'Verbose 404 page', severity: 'low', asset: 'status.acme.io', tool: 'katana', cve: 'CWE-209', verdict: 'tp', status: 'open', evidence: 'Default framework 404 page discloses the backend framework and version', remediation: 'Replace with a generic branded 404 page.' },
  { id: 'f39', name: 'robots.txt discloses internal paths', severity: 'low', asset: '/robots.txt', tool: 'katana', cve: 'CWE-200', verdict: 'tp', status: 'fixed', evidence: 'Disallow entries reveal /internal-admin/ and /debug/ paths to anyone who reads the file', remediation: 'Don\'t rely on robots.txt for access control; remove sensitive paths from it and protect them server-side instead.' },

  // False positives the team already triaged (client never sees these; kept for the Team review page)
  { id: 'fp1', name: 'Verbose error message', severity: 'low', asset: '/api/v1/orders', tool: 'nuclei', cve: 'CWE-209', verdict: 'fp', status: 'open', evidence: 'Stack trace on 500, turned out to be a staging-only debug flag', remediation: 'Suppress stack traces in production; return generic error responses.' },
  { id: 'fp2', name: 'Suspected SQL injection (WAF false trigger)', severity: 'medium', asset: '/rest/products/filter', tool: 'sqlmap', cve: 'CWE-89', verdict: 'fp', status: 'open', evidence: 'Payload triggered a WAF block page, not an actual SQL error; manually confirmed not exploitable', remediation: 'No action needed; consider tuning WAF logging to reduce noise on future scans.' },
  { id: 'fp3', name: 'Self-XSS in browser console', severity: 'low', asset: '/dashboard', tool: 'nuclei', cve: 'CWE-79', verdict: 'fp', status: 'open', evidence: 'Payload only executes if the victim pastes it into their own devtools console', remediation: 'No action needed; not remotely exploitable.' },
  { id: 'fp4', name: 'Outdated library (unreachable code path)', severity: 'medium', asset: '/static/js/legacy.js', tool: 'nuclei', cve: 'CVE-2019-11358', verdict: 'fp', status: 'open', evidence: 'Vulnerable jQuery version present but the vulnerable function is never called from this bundle', remediation: 'Low priority; upgrade opportunistically during the next dependency bump.' },
  { id: 'fp5', name: 'Rate limit alert (legitimate load test)', severity: 'low', asset: '/api/v1/health', tool: 'nuclei', cve: 'CWE-307', verdict: 'fp', status: 'open', evidence: 'Burst of requests correlated with a scheduled internal load test, not an attacker', remediation: 'No action needed; exclude the load-test source IP range from future scans.' },
]

// Per-engagement detail for the review drawer - one entry per board card, so opening any
// card's drawer shows its own real scope/RoE instead of the same hardcoded placeholder.
// version_no/created_at (not n/when) - matches what TeamBoard.tsx's whenOf() and downloadVersion()
// actually consume (the real API's shape); a field-name mismatch here throws inside whenOf's
// .replace() the moment "View details" opens a card with versions.
type Detail = { proposal: { purpose: string; division: string; environment: string; authorized: boolean }; versions?: { version_no: number; editor: string; note: string; created_at: string }[] }
export const engagementDetail: Record<string, Detail> = {
  // Pending approval
  p1: { proposal: { purpose: 'Pre-release', division: 'Business Dev', environment: 'Production', authorized: true } },
  p2: { proposal: { purpose: 'Compliance', division: 'IT', environment: 'Production', authorized: true } },
  p3: { proposal: { purpose: 'Incident', division: 'SecOps', environment: 'Production', authorized: true } },
  p4: { proposal: { purpose: 'Periodic', division: 'Logistics', environment: 'Production', authorized: true } },
  p5: { proposal: { purpose: 'Pre-release', division: 'E-commerce', environment: 'Staging', authorized: true } },
  // Scanning
  s1: { proposal: { purpose: 'Compliance', division: 'Risk & Compliance', environment: 'Production', authorized: true } },
  s2: { proposal: { purpose: 'Periodic', division: 'Platform', environment: 'Staging', authorized: true } },
  s3: { proposal: { purpose: 'Periodic', division: 'Platform', environment: 'Production', authorized: true } },
  s4: { proposal: { purpose: 'Pre-release', division: 'Patient Portal', environment: 'Staging', authorized: true } },
  // Reporter
  r1: {
    proposal: { purpose: 'Pre-release', division: 'Engineering', environment: 'Production', authorized: true },
    versions: [
      { version_no: 1, editor: 'system', note: 'auto-generated v1', created_at: '2026-06-19 09:12:00' },
      { version_no: 2, editor: 'Aisah', note: 'fixed exec summary, marked 2 FPs', created_at: '2026-06-19 14:40:00' },
    ],
  },
  r2: { proposal: { purpose: 'Compliance', division: 'Engineering', environment: 'Production', authorized: true }, versions: [{ version_no: 1, editor: 'Aisah', note: 'auto-generated v1, drafting', created_at: '2026-06-20 10:05:00' }] },
  r3: { proposal: { purpose: 'Periodic', division: 'Fleet Ops', environment: 'Production', authorized: true }, versions: [{ version_no: 1, editor: 'system', note: 'auto-generated v1', created_at: '2026-06-20 08:40:00' }] },
  // Lead
  l1: {
    proposal: { purpose: 'Pre-release', division: 'E-commerce', environment: 'Production', authorized: true },
    versions: [
      { version_no: 1, editor: 'system', note: 'auto-generated v1', created_at: '2026-06-17 11:00:00' },
      { version_no: 2, editor: 'Dimas', note: 'rewrote remediation for 3 findings', created_at: '2026-06-18 09:30:00' },
      { version_no: 3, editor: 'Dimas', note: 'reviewing severity calls', created_at: '2026-06-19 16:12:00' },
    ],
  },
  l2: {
    proposal: { purpose: 'Pre-release', division: 'E-commerce', environment: 'Production', authorized: true },
    versions: [
      { version_no: 1, editor: 'system', note: 'auto-generated v1', created_at: '2026-06-18 13:00:00' },
      { version_no: 2, editor: 'Dimas', note: 'reviewing', created_at: '2026-06-19 09:20:00' },
    ],
  },
  // Governance
  g1: {
    proposal: { purpose: 'Compliance', division: 'Patient Data', environment: 'Production', authorized: true },
    versions: [
      { version_no: 1, editor: 'system', note: 'auto-generated v1', created_at: '2026-06-12 09:00:00' },
      { version_no: 2, editor: 'Riyan', note: 'lead review, 1 FP marked', created_at: '2026-06-14 15:40:00' },
      { version_no: 3, editor: 'Riyan', note: 'severity adjusted per client feedback', created_at: '2026-06-16 11:10:00' },
      { version_no: 4, editor: 'Hani', note: 'final sign-off pass', created_at: '2026-06-17 10:00:00' },
    ],
  },
  g2: {
    proposal: { purpose: 'Compliance', division: 'IT', environment: 'Production', authorized: true },
    versions: [
      { version_no: 1, editor: 'system', note: 'auto-generated v1', created_at: '2026-06-15 09:00:00' },
      { version_no: 2, editor: 'Riyan', note: 'lead review', created_at: '2026-06-16 14:20:00' },
      { version_no: 3, editor: 'Hani', note: 'final sign-off pass', created_at: '2026-06-17 09:45:00' },
    ],
  },
  // Delivered
  d1: { proposal: { purpose: 'Compliance', division: 'IT', environment: 'Production', authorized: true } },
  d2: { proposal: { purpose: 'Pre-release', division: 'Marketing', environment: 'Production', authorized: true } },
  d3: { proposal: { purpose: 'Compliance', division: 'IT', environment: 'Production', authorized: true } },
  d4: { proposal: { purpose: 'Periodic', division: 'Platform', environment: 'Production', authorized: true } },
  d5: { proposal: { purpose: 'Pre-release', division: 'Developer Relations', environment: 'Production', authorized: true } },
  d6: { proposal: { purpose: 'Compliance', division: 'Risk & Compliance', environment: 'Production', authorized: true } },
}
