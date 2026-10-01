import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowUpRight, Plus } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientShell } from '@/components/ClientShell'
import { ErrorRetry } from '@/components/ErrorRetry'
import { ScanProgress } from '@/components/ScanProgress'
import { Gauge } from '@/components/viz/Gauge'
import { SegBar } from '@/components/viz/SegBar'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { useApiData } from '@/lib/useApiData'
import { rise } from '@/lib/motion'
import { bare, when } from '@/lib/format'
import { NewProposalDrawer } from './NewProposalDrawer'

const stageHint: Record<string, string> = {
  pending: 'Waiting for your lead pentester to verify authorization and approve the scan.',
  scanning: 'The agent is running the scan on your machine. Findings stream in as tools finish.',
  in_review: 'Scan complete. The report is moving through reporter, lead, and governance review.',
  delivered: 'Signed off and delivered. The protected report is available on the Reports page.',
  rejected: 'This proposal was not approved. See the reason below - you can submit a corrected proposal any time.',
}

type P = { id: string; target: string; purpose: string; division: string; status: string; when: string; reason?: string; job_id?: string; scan_mode?: string }
const meta: Record<string, { label: string; tone: string }> = {
  pending: { label: 'Pending approval', tone: 'med' },
  scanning: { label: 'Scanning', tone: 'info' },
  in_review: { label: 'In review', tone: 'accent' },
  delivered: { label: 'Delivered', tone: 'low' },
  rejected: { label: 'Rejected', tone: 'crit' },
}
const order = ['pending', 'scanning', 'in_review', 'delivered', 'rejected']

export default function ClientProposals() {
  const nav = useNavigate()
  const { data: rows, error, reload } = useApiData<P[]>(() => api.get('/api/proposals'))
  const [open, setOpen] = useState(false)
  const [sel, setSel] = useState<P | null>(null)
  const revealed = useRef(false)
  useEffect(() => {
    if (rows && !revealed.current) { rise('.entry', 45); revealed.current = true }
  }, [rows])
  // "The agent is running... findings stream in" (stageHint.scanning below) was previously just
  // copy - nothing ever refetched, so a proposal that got approved or finished scanning while you
  // watched wouldn't update until you navigated away and back. Poll while anything's still moving
  // through the pipeline; stop once everything's settled (delivered/rejected). Reusing `reload`
  // means a poll that happens to fail surfaces the same error+retry state a normal load would,
  // instead of failing silently forever in the background.
  useEffect(() => {
    if (!rows?.some((p) => p.status === 'pending' || p.status === 'scanning' || p.status === 'in_review')) return
    const id = setInterval(reload, 8000)
    return () => clearInterval(id)
  }, [rows, reload])

  const list = useMemo(
    () => (rows ?? []).slice().sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status)),
    [rows],
  )
  const c = (s: string) => list.filter((p) => p.status === s).length
  const maxCount = Math.max(1, ...order.map(c))
  const cleared = list.length ? Math.round(((list.length - c('pending') - c('rejected')) / list.length) * 100) : 0

  return (
    <ClientShell
      title="Proposals"
      sub="Every scan starts here. Approved by your lead pentester before it runs."
      action={<Button variant="glass" size="pill" onClick={() => setOpen(true)}><Plus size={16} /> New Proposal</Button>}
    >
      {error ? (
        <ErrorRetry message={error} onRetry={reload} />
      ) : !rows ? (
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
                {c('rejected') > 0 && <SegBar label="Rejected" count={c('rejected')} max={maxCount} tone="crit" />}
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
                  <button onClick={() => setSel(p)} className="group flex w-full items-center gap-4 border-b border-rule px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-panel">
                    <span className="flex w-[128px] flex-none items-center gap-2">
                      <span className="h-2.5 w-2.5 flex-none rounded-full" style={{ background: `var(--color-${meta[p.status].tone})` }} />
                      <span className="text-[12px] text-ink-muted">{meta[p.status].label}</span>
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15.5px] font-medium text-ink" title={p.target}>{bare(p.target)}</span>
                      <span className="mt-0.5 block truncate text-[12px] text-ink-faint">{p.purpose}, {p.division} · {p.scan_mode === 'cloud' ? 'Cloud scan' : 'Local scan'}</span>
                    </span>
                    <span className="mono hidden flex-none text-[12px] text-ink-faint sm:block">{when(p.when)}</span>
                    <span className="grid h-8 w-8 flex-none place-items-center rounded-full border border-rule text-ink-faint opacity-0 transition-opacity duration-200 group-hover:text-ink group-hover:opacity-100"><ArrowUpRight size={15} /></span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
      <NewProposalDrawer open={open} onOpenChange={setOpen} />

      <Drawer open={!!sel} onOpenChange={(v) => !v && setSel(null)}>
        {sel && (
          <DrawerContent>
            <div className="border-b border-rule p-6">
              <span className="inline-flex items-center gap-2 rounded-pill bg-panel px-[11px] py-1.5 text-[11.5px] font-semibold text-ink-muted">
                <span className="h-2 w-2 rounded-full" style={{ background: `var(--color-${meta[sel.status].tone})` }} />
                {meta[sel.status].label}
              </span>
              <DrawerTitle className="mt-2.5 text-[22px] font-bold tracking-[-0.02em] text-ink">{sel.target}</DrawerTitle>
              <p className="mono mt-1 text-[13px] text-ink-muted">Submitted {when(sel.when)}</p>
            </div>
            <div className="flex-1 space-y-5 p-6">
              <div className="rounded-input border border-rule bg-panel p-4 text-[13.5px] leading-relaxed text-ink">{stageHint[sel.status]}</div>
              {sel.status === 'scanning' && sel.job_id && (
                <div className="rounded-input border border-rule bg-panel p-4">
                  <ScanProgress jobId={sel.job_id} />
                </div>
              )}
              {sel.status === 'rejected' && sel.reason && (
                <div className="rounded-input border border-crit-bg bg-crit-bg p-4 text-[13.5px] leading-relaxed text-crit">{sel.reason}</div>
              )}
              {[['Purpose', sel.purpose], ['Division', sel.division], ['Scan runs', sel.scan_mode === 'cloud' ? 'By Varuna (cloud)' : 'On your computer']].map(([l, v]) => (
                <div key={l} className="flex items-center justify-between border-b border-rule pb-3 last:border-b-0">
                  <span className="text-[13px] text-ink-muted">{l}</span>
                  <b className="text-[13.5px] font-semibold text-ink">{v}</b>
                </div>
              ))}
            </div>
            {sel.status === 'delivered' && (
              <div className="sticky bottom-0 border-t border-rule bg-card p-6">
                <Button size="lg" className="w-full" onClick={() => { setSel(null); nav('/reports') }}>View report <ArrowUpRight size={16} /></Button>
              </div>
            )}
          </DrawerContent>
        )}
      </Drawer>
    </ClientShell>
  )
}
