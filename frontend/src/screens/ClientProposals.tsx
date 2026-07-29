import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, CheckCircle2, Loader, Plus, ScanLine } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { StatRing } from '@/components/StatRing'
import { revealTiles } from '@/lib/motion'
import { NewProposalDrawer } from './NewProposalDrawer'

const badge: Record<string, string> = {
  in_review: 'bg-accent-soft text-accent-ink', delivered: 'bg-low-bg text-low',
  scanning: 'bg-[rgba(125,151,216,.16)] text-info', pending: 'bg-med-bg text-med',
}
const badgeLabel: Record<string, string> = {
  in_review: 'In review', delivered: 'Delivered', scanning: 'Scanning', pending: 'Pending approval',
}

// Client proposals: a compact activity ledger over engagement cards, the cockpit's tile
// language, not a CRUD table.
export default function ClientProposals() {
  const [rows, setRows] = useState<any[] | null>(null)
  const [open, setOpen] = useState(false)
  useEffect(() => { api.get('/api/proposals').then(setRows) }, [])
  useEffect(() => { if (rows) revealTiles('.tile') }, [rows])

  const n = useMemo(() => {
    const r = rows ?? []
    return { total: r.length, scanning: r.filter((x) => x.status === 'scanning').length, review: r.filter((x) => x.status === 'in_review').length, delivered: r.filter((x) => x.status === 'delivered').length }
  }, [rows])

  return (
    <ClientShell
      title="Proposals"
      sub="Every scan starts here. Approved by your lead pentester before it runs."
      action={<Button variant="glass" size="pill" onClick={() => setOpen(true)}><Plus size={16} /> New Proposal</Button>}
    >
      {!rows ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="flex flex-col gap-3">
          {/* Activity ledger */}
          <section className="tile rounded-bento border border-rule bg-card-2 p-5" style={{ opacity: 0 }}>
            <div className="grid grid-cols-2 gap-x-5 gap-y-5 sm:grid-cols-4">
              <StatRing tone="s" n={n.total} label="Total engagements" icon={<ScanLine size={20} />} />
              <StatRing tone="o" n={n.scanning} label="Scanning now" icon={<Loader size={20} />} />
              <StatRing tone="m" n={n.review} label="In review" icon={<ArrowUpRight size={20} />} />
              <StatRing tone="l" n={n.delivered} label="Delivered" icon={<CheckCircle2 size={20} />} />
            </div>
          </section>

          {/* Engagement cards */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {rows.map((r) => (
              <article key={r.id} className="tile flex flex-col rounded-bento border border-rule bg-card p-5" style={{ opacity: 0 }}>
                <div className="flex items-start justify-between gap-3">
                  <span className={`rounded-pill px-[11px] py-1.5 text-[11.5px] font-semibold ${badge[r.status]}`}>{badgeLabel[r.status]}</span>
                  <span className="text-[12px] text-ink-faint">{r.when}</span>
                </div>
                <h3 className="mt-3.5 text-[17px] font-bold tracking-[-0.02em] text-ink">{r.target}</h3>
                <p className="mt-1 text-[13px] text-ink-muted">{r.detail}</p>
                <div className="mt-4 flex items-center justify-between border-t border-rule pt-3.5">
                  <span className="text-[12px] text-ink-faint">{r.status === 'delivered' ? 'Report available' : r.status === 'scanning' ? 'Live scan running' : 'Awaiting review'}</span>
                  <button onClick={(e) => e.currentTarget.blur()} className="flex items-center gap-1 text-[12.5px] font-semibold text-accent-ink hover:text-accent">
                    View <ArrowUpRight size={14} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}
      <NewProposalDrawer open={open} onOpenChange={setOpen} />
    </ClientShell>
  )
}
