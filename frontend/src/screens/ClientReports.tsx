import { useEffect, useState } from 'react'
import { Download, FileText, Lock, ShieldCheck } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { revealTiles } from '@/lib/motion'

type Report = { id: string; engagement: string; delivered: string; findings: number; templates: string[]; signed: boolean }

function PasswordRow({ id, shown, onReveal }: { id: string; shown: boolean; onReveal: () => void }) {
  if (shown)
    return (
      <div className="mt-[11px] flex items-center justify-center gap-2 rounded-input border border-dashed border-accent-soft bg-accent-soft/40 py-2.5 font-mono text-[13px] font-semibold text-accent-ink">
        <Lock size={13} /> Xk9-{id}-view1 · copied
      </div>
    )
  return (
    <button onClick={onReveal} className="mt-[11px] flex w-full items-center justify-center gap-[7px] text-[12.5px] font-semibold text-ink-muted hover:text-ink">
      <Lock size={14} /> Reveal password (view-once)
    </button>
  )
}

// Client reports: one featured latest deliverable, then a quiet list of older ones, hierarchy
// over the flat two-card grid.
export default function ClientReports() {
  const [rows, setRows] = useState<Report[] | null>(null)
  const [shown, setShown] = useState<string | null>(null)
  useEffect(() => { api.get('/api/reports').then(setRows) }, [])
  useEffect(() => { if (rows) revealTiles('.tile') }, [rows])

  const featured = rows?.[0]
  const rest = rows?.slice(1) ?? []

  return (
    <ClientShell title="Reports" sub="Signed-off deliverables. Each PDF is read-only; its password is shown once.">
      {!rows ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="flex flex-col gap-3">
          {/* Featured latest report */}
          {featured && (
            <section className="tile grid grid-cols-1 gap-6 rounded-bento border border-rule bg-card-2 p-6 lg:grid-cols-[1.4fr_1fr]" style={{ opacity: 0 }}>
              <div>
                <span className="text-[12px] font-semibold uppercase tracking-wide text-accent">Latest deliverable</span>
                <h2 className="mt-2 text-[clamp(22px,3vw,30px)] font-bold leading-tight tracking-[-0.02em] text-ink">{featured.engagement}</h2>
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px] text-ink-muted">
                  <span>Delivered {featured.delivered}</span>
                  <span className="text-ink-faint">·</span>
                  <span>{featured.findings} findings</span>
                  {featured.signed && <span className="flex items-center gap-1.5 text-low"><ShieldCheck size={14} /> Governance signed</span>}
                </div>
                <div className="mt-5 flex flex-wrap gap-1.5">
                  {featured.templates.map((t) => (
                    <span key={t} className="rounded-pill border border-rule bg-panel px-3 py-1.5 text-[12px] font-medium text-ink-muted">{t}</span>
                  ))}
                </div>
              </div>
              <div className="flex flex-col justify-center rounded-bento border border-rule bg-card p-5">
                <Button size="lg" className="w-full"><Download size={17} /> Download protected PDF</Button>
                <PasswordRow id={featured.id} shown={shown === featured.id} onReveal={() => setShown(featured.id)} />
                <p className="mt-3 text-center text-[11.5px] leading-relaxed text-ink-faint">Password is out-of-band from the file and shown once. Re-request from governance if lost.</p>
              </div>
            </section>
          )}

          {/* Older reports, quiet list */}
          {rest.length > 0 && (
            <section className="tile rounded-bento border border-rule bg-card p-2" style={{ opacity: 0 }}>
              {rest.map((r) => (
                <div key={r.id} className="flex flex-wrap items-center gap-4 rounded-[16px] px-4 py-3.5 transition-colors hover:bg-panel/60">
                  <span className="grid h-10 w-10 flex-none place-items-center rounded-[11px] border border-rule text-accent"><FileText size={18} /></span>
                  <div className="min-w-0 flex-1">
                    <b className="block text-[14.5px] font-semibold text-ink">{r.engagement}</b>
                    <span className="text-[12.5px] text-ink-muted">{r.delivered} · {r.findings} findings · {r.templates.length} templates</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <button onClick={() => setShown(r.id)} className="text-[12px] font-semibold text-ink-muted hover:text-ink">{shown === r.id ? 'Xk9-' + r.id + '-view1' : 'Password'}</button>
                    <Button variant="outline" size="sm"><Download size={15} /> PDF</Button>
                  </div>
                </div>
              ))}
            </section>
          )}
        </div>
      )}
    </ClientShell>
  )
}
