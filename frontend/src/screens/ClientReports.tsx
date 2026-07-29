import { useEffect, useState } from 'react'
import { CalendarDays, Download, FileText, Lock, ShieldCheck } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'

type Report = { id: string; engagement: string; delivered: string; findings: number; templates: string[]; signed: boolean }

// Client's delivered reports: protected-PDF download + view-once password per engagement.
export default function ClientReports() {
  const [rows, setRows] = useState<Report[] | null>(null)
  const [shown, setShown] = useState<string | null>(null)
  useEffect(() => { api.get('/api/reports').then(setRows) }, [])

  return (
    <ClientShell title="Reports" sub="Signed-off deliverables. Each PDF is read-only; its password is shown once.">
      {!rows ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {rows.map((r) => (
            <section key={r.id} className="flex flex-col rounded-bento border border-rule bg-card p-5">
              <div className="mb-4 flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-[17px] font-bold tracking-[-0.02em] text-ink">{r.engagement}</h3>
                  <div className="mt-1 flex items-center gap-3 text-[12.5px] text-ink-muted">
                    <span className="flex items-center gap-1.5"><CalendarDays size={13} /> {r.delivered}</span>
                    <span>· {r.findings} findings</span>
                  </div>
                </div>
                {r.signed && <span className="flex flex-none items-center gap-1.5 rounded-pill bg-low-bg px-2.5 py-1 text-[11px] font-semibold text-low"><ShieldCheck size={13} /> Signed</span>}
              </div>

              <div className="mb-4 flex flex-wrap gap-1.5">
                {r.templates.map((t) => (
                  <span key={t} className="flex items-center gap-1.5 rounded-pill border border-rule bg-panel px-2.5 py-1 text-[11.5px] font-medium text-ink-muted"><FileText size={12} /> {t}</span>
                ))}
              </div>

              <div className="mt-auto">
                <Button size="lg" className="w-full"><Download size={17} /> Download protected PDF</Button>
                {shown === r.id ? (
                  <div className="mt-[11px] flex items-center justify-center gap-2 rounded-input border border-dashed border-accent-soft bg-accent-soft/40 py-2.5 font-mono text-[13px] font-semibold text-accent-ink">
                    <Lock size={13} /> Xk9-{r.id}-view1 · copied
                  </div>
                ) : (
                  <button onClick={() => setShown(r.id)} className="mt-[11px] flex w-full items-center justify-center gap-[7px] text-[12.5px] font-semibold text-ink-muted hover:text-ink">
                    <Lock size={14} /> Reveal password (view-once)
                  </button>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </ClientShell>
  )
}
