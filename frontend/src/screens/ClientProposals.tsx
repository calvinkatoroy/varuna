import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, Plus } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { Gauge } from '@/components/viz/Gauge'
import { SegBar } from '@/components/viz/SegBar'
import { rise } from '@/lib/motion'
import { NewProposalDrawer } from './NewProposalDrawer'

type P = { id: string; target: string; purpose: string; division: string; status: string; when: string }
const meta: Record<string, { label: string; tone: string }> = {
  pending: { label: 'Pending approval', tone: 'med' },
  scanning: { label: 'Scanning', tone: 'info' },
  in_review: { label: 'In review', tone: 'accent' },
  delivered: { label: 'Delivered', tone: 'low' },
}
const order = ['pending', 'scanning', 'in_review', 'delivered']

export default function ClientProposals() {
  const [rows, setRows] = useState<P[] | null>(null)
  const [open, setOpen] = useState(false)
  useEffect(() => { api.get('/api/proposals').then(setRows) }, [])
  useEffect(() => { if (rows) rise('.entry', 45) }, [rows])

  const list = useMemo(
    () => (rows ?? []).slice().sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status)),
    [rows],
  )
  const c = (s: string) => list.filter((p) => p.status === s).length
  const maxCount = Math.max(1, ...order.map(c))
  const cleared = list.length ? Math.round(((list.length - c('pending')) / list.length) * 100) : 0

  return (
    <ClientShell
      title="Proposals"
      sub="Every scan starts here. Approved by your lead pentester before it runs."
      action={<Button variant="glass" size="pill" onClick={() => setOpen(true)}><Plus size={16} /> New Proposal</Button>}
    >
      {!rows ? (
        <div className="p-10 text-ink-faint">Loading</div>
      ) : (
        <div className="flex flex-col gap-3">
          <section className="grid grid-cols-1 gap-6 rounded-bento border border-rule bg-card p-6 lg:grid-cols-[1fr_auto] lg:gap-10">
            <div className="min-w-0">
              <div className="flex items-baseline gap-2.5">
                <span className="font-display text-[46px] font-bold leading-none tracking-[-0.03em] text-ink">{list.length}</span>
                <span className="text-[14px] text-ink-muted">engagements</span>
              </div>
              <div className="mt-6 flex flex-col gap-3">
                <SegBar label="Pending" count={c('pending')} max={maxCount} tone="med" />
                <SegBar label="Scanning" count={c('scanning')} max={maxCount} tone="info" />
                <SegBar label="In review" count={c('in_review')} max={maxCount} tone="accent" />
                <SegBar label="Delivered" count={c('delivered')} max={maxCount} tone="low" />
              </div>
            </div>
            <div className="flex items-center justify-center border-t border-rule pt-4 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
              <Gauge value={cleared} label="Approved" tone="accent" />
            </div>
          </section>

          <section className="rounded-bento border border-rule bg-card">
            <ul>
              {list.map((p) => (
                <li key={p.id} className="entry" style={{ opacity: 0 }}>
                  <button className="group flex w-full items-center gap-4 border-b border-rule px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-panel">
                    <span className="flex w-[128px] flex-none items-center gap-2">
                      <span className="h-2.5 w-2.5 flex-none rounded-full" style={{ background: `var(--color-${meta[p.status].tone})` }} />
                      <span className="text-[12px] text-ink-muted">{meta[p.status].label}</span>
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15.5px] font-medium text-ink">{p.target}</span>
                      <span className="mt-0.5 block truncate text-[12px] text-ink-faint">{p.purpose}, {p.division}</span>
                    </span>
                    <span className="mono hidden flex-none text-[12px] text-ink-faint sm:block">{p.when}</span>
                    <span className="grid h-8 w-8 flex-none place-items-center rounded-full border border-rule text-ink-faint opacity-0 transition-opacity duration-200 group-hover:text-ink group-hover:opacity-100"><ArrowUpRight size={15} /></span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
      <NewProposalDrawer open={open} onOpenChange={setOpen} />
    </ClientShell>
  )
}
