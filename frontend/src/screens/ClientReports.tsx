import { useEffect, useState } from 'react'
import { Check, Download, Lock, ShieldCheck } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { rise } from '@/lib/motion'

type Report = { id: string; engagement: string; delivered: string; findings: number; templates: string[]; signed: boolean }
const chip = 'rounded-md border border-rule bg-panel px-2 py-1 text-[11.5px] text-ink-muted'

function Password({ id, shown, onReveal }: { id: string; shown: boolean; onReveal: () => void }) {
  if (shown)
    return <span className="mono flex items-center gap-1.5 text-[12.5px] font-medium text-accent-ink"><Lock size={13} /> Xk9{id}v1</span>
  return (
    <button onClick={onReveal} className="flex items-center gap-1.5 text-[12.5px] font-medium text-ink-muted transition-colors hover:text-ink">
      <Lock size={13} /> Password
    </button>
  )
}

export default function ClientReports() {
  const [rows, setRows] = useState<Report[] | null>(null)
  const [shown, setShown] = useState<string | null>(null)
  useEffect(() => { api.get('/api/reports').then(setRows) }, [])
  useEffect(() => { if (rows) rise('.entry', 60) }, [rows])

  const [got, setGot] = useState<Record<string, boolean>>({})
  const download = (id: string) => setGot((g) => ({ ...g, [id]: true }))
  const featured = rows?.[0]
  const rest = rows?.slice(1) ?? []

  return (
    <ClientShell title="Reports" sub="Signed deliverables. Each PDF is read only, its password is shown once.">
      {!rows ? (
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
                <div className="flex justify-center"><Password id={featured.id} shown={shown === featured.id} onReveal={() => setShown(featured.id)} /></div>
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
                      <Password id={r.id} shown={shown === r.id} onReveal={() => setShown(r.id)} />
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
