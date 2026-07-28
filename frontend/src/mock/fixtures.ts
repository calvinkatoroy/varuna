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
