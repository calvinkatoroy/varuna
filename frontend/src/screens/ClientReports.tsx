import { useEffect, useState } from 'react'
import { Check, Download, Lock, ShieldCheck } from 'lucide-react'
import { api, download as downloadFile } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { ErrorRetry } from '@/components/ErrorRetry'
import { useApiData } from '@/lib/useApiData'
import { rise } from '@/lib/motion'

type Report = { id: string; engagement: string; delivered: string; findings: number; templates: string[]; signed: boolean }
const chip = 'rounded-md border border-rule bg-panel px-2 py-1 text-[11.5px] text-ink-muted'

// Reveals the real view-once password (GET /api/reports/{id}/password) rather than a fake
// client-side string - the endpoint itself enforces "once": a second reveal 403s, so this
// component doesn't need its own "already viewed" bookkeeping beyond what it just fetched.
function Password({ id }: { id: string }) {
  const [pw, setPw] = useState<string | null>(null)
  const [err, setErr] = useState(false)
  if (pw) return <span className="mono flex items-center gap-1.5 text-[12.5px] font-medium text-accent-ink"><Lock size={13} /> {pw}</span>
  if (err) return <span className="text-[12.5px] text-ink-faint">Already viewed - ask governance to re-issue.</span>
  return (
    <button
      onClick={() => api.get(`/api/reports/${id}/password`).then((r) => setPw(r.password)).catch(() => setErr(true))}
      className="flex items-center gap-1.5 text-[12.5px] font-medium text-ink-muted transition-colors hover:text-ink"
    >
      <Lock size={13} /> Password
    </button>
  )
}

export default function ClientReports() {
  const { data: rows, error, reload } = useApiData<Report[]>(() => api.get('/api/reports'))
  useEffect(() => { if (rows) rise('.entry', 60) }, [rows])

  const [got, setGot] = useState<Record<string, boolean>>({})
  // Only marks "Downloaded" once the file actually came back - downloadFile() throws on
  // failure (report not delivered yet, file missing), which used to leave the button showing
  // a checkmark for a download that never happened.
  const download = (id: string) => {
    downloadFile(api.publicBase, `/api/reports/${id}/delivered`, `${id}.pdf`)
      .then(() => setGot((g) => ({ ...g, [id]: true })))
      .catch(() => {})
  }
  const featured = rows?.[0]
  const rest = rows?.slice(1) ?? []

  return (
    <ClientShell title="Reports" sub="Signed deliverables. Each PDF is read only, its password is shown once.">
      {error ? (
        <ErrorRetry message={error} onRetry={reload} />
      ) : !rows ? (
        <div className="p-10 text-ink-faint">Loading</div>
      ) : (
        <div className="flex flex-col gap-3">
          {featured && (
            <section className="entry grid grid-cols-1 gap-6 rounded-bento border border-rule bg-card p-6 lg:grid-cols-[1.5fr_1fr]" style={{ opacity: 0 }}>
              <div className="min-w-0">
                <span className="text-[11.5px] font-medium uppercase tracking-[0.12em] text-accent">Latest report</span>
                <h2 className="mt-2 text-[clamp(22px,3vw,30px)] font-bold leading-tight tracking-[-0.02em] text-ink">{featured.engagement}</h2>
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px] text-ink-muted">
                  <span>Delivered {featured.delivered}</span>
                  <span>{featured.findings} findings</span>
                  {featured.signed && <span className="flex items-center gap-1.5 text-low"><ShieldCheck size={14} /> Governance signed</span>}
                </div>
                <div className="mt-5 flex flex-wrap gap-1.5">
                  {featured.templates.map((t) => <span key={t} className={chip}>{t}</span>)}
                </div>
              </div>
              <div className="flex flex-col justify-center gap-3 border-t border-rule pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
                <Button size="lg" className="w-full" onClick={() => download(featured.id)}>{got[featured.id] ? <><Check size={17} /> Downloaded</> : <><Download size={17} /> Download protected PDF</>}</Button>
                <div className="flex justify-center"><Password id={featured.id} /></div>
                <p className="text-center text-[11.5px] leading-relaxed text-ink-faint">Password is out of band from the file. Re-request from governance if lost.</p>
              </div>
            </section>
          )}

          {rest.length > 0 && (
            <section className="entry rounded-bento border border-rule bg-card" style={{ opacity: 0 }}>
              <ul>
                {rest.map((r) => (
                  <li key={r.id}>
                    <div className="flex flex-wrap items-center gap-4 border-b border-rule px-5 py-4 last:border-b-0">
                      <div className="min-w-0 flex-1">
                        <b className="block truncate text-[15px] font-medium text-ink">{r.engagement}</b>
                        <span className="text-[12px] text-ink-faint">{r.delivered}, {r.findings} findings, {r.templates.length} templates</span>
                      </div>
                      <Password id={r.id} />
                      <Button variant="outline" size="sm" onClick={() => download(r.id)}>{got[r.id] ? <><Check size={15} /> Got it</> : <><Download size={15} /> PDF</>}</Button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </ClientShell>
  )
}
