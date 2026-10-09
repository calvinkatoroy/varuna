// Mock findings by target (VITE_MOCK=1), mirroring the routes of controlplane/api/browser.py.
const fail = (status: number, message: string) => Object.assign(new Error(message), { status })

type Row = {
  id: string; task_id: string; name: string; severity: string; host: string; url: string; tool: string
  cve: string | null; cwe: string | null; verdict: 'tp' | 'fp'; status: 'open' | 'fixed'
  evidence: string; remediation: string | null; description: string | null; impact: string | null
}

const SAMUDERA = 'PT Samudera Logistik'
const TARGETS = [
  { task_id: 't4', target: 'https://app.samudera.co.id', host: 'app.samudera.co.id', org_name: SAMUDERA, scanned_at: '2026-09-30 14:20:00', count: 520 },
  { task_id: 't1', target: 'https://portal.samudera.co.id', host: 'portal.samudera.co.id', org_name: SAMUDERA, scanned_at: '2026-10-08 09:10:00', count: 18 },
  { task_id: 't2', target: 'https://tracking.samudera.co.id', host: 'tracking.samudera.co.id', org_name: SAMUDERA, scanned_at: '2026-10-08 11:40:00', count: 9 },
  { task_id: 't3', target: 'http://10.0.4.12', host: '10.0.4.12', org_name: SAMUDERA, scanned_at: '2026-10-05 08:30:00', count: 4 },
  { task_id: 't9', target: 'https://bongkar.nusantarapelabuhan.co.id', host: 'bongkar.nusantarapelabuhan.co.id', org_name: 'PT Nusantara Pelabuhan', scanned_at: '2026-10-07 16:00:00', count: 30 },
]

const KINDS = [
  { name: 'SQL Injection', severity: 'critical', tool: 'sqlmap', cwe: 'CWE-89', path: '/api/pelanggan/cari?q=', evidence: "q=1' AND SLEEP(5)-- -  ->  respons 10,0 detik", fix: 'Gunakan prepared statement, validasi semua input, dan batasi hak akun database.' },
  { name: 'Broken access control', severity: 'critical', tool: 'nuclei', cwe: 'CWE-284', path: '/api/admin/pengguna/', evidence: 'Token pengguna biasa dapat membaca data semua pelanggan', fix: 'Terapkan otorisasi di sisi server untuk setiap objek; tolak secara default.' },
  { name: 'Reflected XSS', severity: 'high', tool: 'nuclei', cwe: 'CWE-79', path: '/pencarian?kata=', evidence: '<script>alert(1)</script> muncul tanpa di-encode pada respons', fix: 'Encode output sesuai konteks dan pasang Content-Security-Policy yang ketat.' },
  { name: 'Stored XSS', severity: 'high', tool: 'nuclei', cwe: 'CWE-79', path: '/api/profil/', evidence: 'Kolom bio menampilkan HTML mentah kepada setiap pengunjung', fix: 'Sanitasi saat menyimpan dan encode saat menampilkan.' },
  { name: 'Weak TLS ciphers', severity: 'high', tool: 'nuclei', cwe: 'CWE-327', path: ':443/', evidence: 'TLS 1.0 dan RC4 masih diterima di listener utama', fix: 'Matikan TLS di bawah 1.2 dan cipher lama; pakai AES-GCM atau ChaCha20.' },
  { name: 'Missing HSTS header', severity: 'medium', tool: 'nuclei', cwe: 'CWE-319', path: '/halaman/', evidence: 'Tidak ada header Strict-Transport-Security pada respons HTTPS', fix: 'Tambahkan Strict-Transport-Security: max-age=31536000; includeSubDomains.' },
  { name: 'Open redirect', severity: 'medium', tool: 'katana', cwe: 'CWE-601', path: '/masuk?next=', evidence: 'Parameter next mengarahkan ke situs luar tanpa pemeriksaan', fix: 'Validasi tujuan redirect terhadap daftar putih di server.' },
  { name: 'Directory listing enabled', severity: 'low', tool: 'katana', cwe: 'CWE-548', path: '/unggah/', evidence: 'Autoindex menampilkan berkas yang diunggah', fix: 'Matikan autoindex pada konfigurasi web server.' },
  { name: 'Cookie without Secure flag', severity: 'low', tool: 'nuclei', cwe: 'CWE-614', path: '/sesi/', evidence: 'Cookie sesi dikirim tanpa atribut Secure', fix: 'Set Secure, HttpOnly dan SameSite pada semua cookie sesi.' },
  { name: 'Server banner discloses version', severity: 'info', tool: 'nuclei', cwe: 'CWE-200', path: '/', evidence: 'Header Server menyebut nginx/1.18.0', fix: 'Sembunyikan versi pada header Server (server_tokens off).' },
  { name: 'robots.txt discloses internal paths', severity: 'info', tool: 'katana', cwe: 'CWE-200', path: '/robots.txt#', evidence: 'Entri Disallow menyebut /internal-admin/', fix: 'Jangan andalkan robots.txt untuk kontrol akses.' },
]

const rows: Row[] = TARGETS.flatMap((t, ti) =>
  Array.from({ length: t.count }, (_, i): Row => {
    const k = KINDS[(i * 7 + ti * 3) % KINDS.length]
    return {
      id: `f-${t.task_id}-${String(i).padStart(3, '0')}`, task_id: t.task_id, name: k.name, severity: k.severity,
      host: t.host, url: `${t.target}${k.path}${i + 1}`, tool: k.tool, cve: null, cwe: k.cwe,
      verdict: i % 9 === 8 ? 'fp' : 'tp', status: i % 5 === 4 ? 'fixed' : 'open',
      evidence: k.evidence, remediation: k.fix, description: null, impact: null,
    }
  }),
)

const RANK = ['critical', 'high', 'medium', 'low', 'info']
const rank = (s: string) => { const i = RANK.indexOf(s); return i < 0 ? RANK.length - 1 : i }
const org = (taskId: string) => TARGETS.find((t) => t.task_id === taskId)?.org_name ?? 'Internal'
// Staff see every verdict of every organization; the mock client belongs to PT Samudera and sees confirmed rows only.
const visible = (r: Row, staff: boolean) => staff || (r.verdict === 'tp' && org(r.task_id) === SAMUDERA)
const order = (a: Row, b: Row) => rank(a.severity) - rank(b.severity) || a.name.localeCompare(b.name) || (a.id < b.id ? -1 : 1)
const summary = ({ evidence, remediation, description, impact, ...rest }: Row) => rest

const enc = (n: number) => btoa(`o${n}`).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
const dec = (c: string): number => {
  try {
    const m = atob(c.replace(/-/g, '+').replace(/_/g, '/')).match(/^o(\d+)$/)
    if (m) return Number(m[1])
  } catch { /* falls through */ }
  throw fail(422, 'bad cursor')
}

function targetsFor(staff: boolean) {
  return TARGETS.filter((t) => staff || t.org_name === SAMUDERA)
    .map((t) => {
      const mine = rows.filter((r) => r.task_id === t.task_id && visible(r, staff))
      const counts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 }
      mine.forEach((r) => { counts[r.severity] += 1 })
      return {
        task_id: t.task_id, target: t.target, total: mine.length, fixed: mine.filter((r) => r.status === 'fixed').length,
        scanned_at: t.scanned_at, counts, ...(staff ? { org_name: t.org_name, fp: mine.filter((r) => r.verdict === 'fp').length } : {}),
      }
    })
    .filter((t) => t.total > 0)
    .sort((a, b) => b.scanned_at.localeCompare(a.scanned_at))   // newest scan first, like the server
}

function pageFor(u: URLSearchParams, staff: boolean) {
  const taskId = u.get('task_id')!
  let list = rows.filter((r) => r.task_id === taskId && visible(r, staff))
  if (!list.length) throw fail(404, 'no such target')
  const sev = u.get('severity')?.toLowerCase()
  if (sev) list = list.filter((r) => r.severity === sev)
  list = list.slice().sort(order)
  const limit = Math.min(200, Math.max(1, Number(u.get('limit') ?? 100)))
  let start = u.get('cursor') ? dec(u.get('cursor')!) : 0
  let size = limit
  const upto = u.get('upto')
  if (upto) {
    const at = list.findIndex((r) => r.id === upto)
    if (at < 0) throw fail(404, 'no such target')
    start = 0
    size = (Math.floor(at / limit) + 1) * limit
  }
  const items = list.slice(start, start + size).map(summary)
  const end = start + items.length
  return { items, next_cursor: end < list.length ? enc(end) : null, total: list.length }
}

export function findingsRoute(m: string, path: string, body: any, staff: boolean): any {
  const u = new URL(path, 'http://mock')
  const p = u.pathname
  if (m === 'GET' && p === '/api/scans') return []
  if (m === 'GET' && p === '/api/quick-scans') return []
  if (m === 'POST' && p === '/api/quick-scans') return { job_id: 'mock-quick', state: 'dispatched' }
  if (m === 'GET' && p === '/api/findings/targets') return targetsFor(staff)
  if (m === 'GET' && p === '/api/findings') {
    if (u.searchParams.get('task_id')) return pageFor(u.searchParams, staff)
    return rows.filter((r) => visible(r, staff)).map((r) => (staff ? { ...r, org_name: org(r.task_id) } : r))   // the old flat list
  }
  const one = m === 'GET' && p.match(/^\/api\/findings\/id\/([^/]+)$/)
  if (one) {
    const r = rows.find((x) => x.id === decodeURIComponent(one[1]))
    if (!r || !visible(r, staff)) throw fail(404, 'no such finding')
    return staff ? { ...r, org_name: org(r.task_id) } : r
  }
  const act = m === 'POST' && p.match(/^\/api\/findings\/([^/]+)\/(status|verdict)$/)
  if (act) {
    const r = rows.find((x) => x.id === decodeURIComponent(act[1]))
    if (!r || !visible(r, staff)) throw fail(404, 'no such finding')
    if (act[2] === 'status') r.status = body.status
    else r.verdict = body.verdict
    return { ok: true }
  }
  return undefined
}
