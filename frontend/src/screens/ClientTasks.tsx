import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowUpRight, Plus } from 'lucide-react'
import { tasks, type ClientTask, type TimelineItem } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientPage } from '@/components/ClientPage'
import { ErrorRetry } from '@/components/ErrorRetry'
import { ScanProgress } from '@/components/ScanProgress'
import { SegBar } from '@/components/viz/SegBar'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { useApiData } from '@/lib/useApiData'
import { FEEDS } from '@/lib/feeds'
import { bare, localTime, when } from '@/lib/format'
import { CLIENT_HINT, CLIENT_LABEL, CLIENT_ORDER, CLIENT_TONE, isClosed } from '@/lib/workflow'
import { NewTaskDrawer } from './NewTaskDrawer'

const dotStyle = (s: ClientTask['status']) => ({ background: `var(--color-${CLIENT_TONE[s]})` })

export default function ClientTasks() {
  const nav = useNavigate()
  const { data: rows, error, reload } = useApiData<ClientTask[]>(FEEDS.tasks.load, FEEDS.tasks.key)
  const [open, setOpen] = useState(false)
  const [sel, setSel] = useState<ClientTask | null>(null)
  const [timeline, setTimeline] = useState<TimelineItem[]>([])
  // Poll while anything is still moving; stop once everything has settled.
  useEffect(() => {
    if (!rows?.some((t) => !isClosed(t.status) && t.status !== 'delivered')) return
    const id = setInterval(reload, 8000)
    return () => clearInterval(id)
  }, [rows, reload])
  useEffect(() => {
    setTimeline([])
    if (sel) tasks.timeline(sel.id).then(setTimeline).catch(() => {})
  }, [sel])

  const list = useMemo(() => (rows ?? []).slice().sort((a, b) => CLIENT_ORDER.indexOf(a.status) - CLIENT_ORDER.indexOf(b.status)), [rows])
  const count = (s: ClientTask['status']) => list.filter((t) => t.status === s).length
  const max = Math.max(1, ...CLIENT_ORDER.map(count))

  return (
    <ClientPage
      title="Tasks"
      sub="Every scan starts here. A pentester plans it inside your time limit."
      action={<Button variant="glass" size="pill" onClick={() => setOpen(true)}><Plus size={16} /> New task</Button>}
    >
      {error ? (
        <ErrorRetry message={error} onRetry={reload} />
      ) : !rows ? (
        <div className="p-10 text-ink-faint">Loading</div>
      ) : (
        <div className="flex flex-col gap-3">
          <section className="rounded-bento border border-rule bg-card p-6">
            <div className="flex items-baseline gap-2.5">
              <span className="font-display text-[46px] font-bold leading-none tracking-[-0.03em] text-ink">{list.length}</span>
              <span className="text-[14px] text-ink-muted">tasks</span>
            </div>
            <div className="mt-6 flex flex-col gap-3">
              {CLIENT_ORDER.filter((s) => count(s) > 0).map((s) => (
                <SegBar key={s} label={CLIENT_LABEL[s]} count={count(s)} max={max} tone={CLIENT_TONE[s]} labelW={150} />
              ))}
            </div>
          </section>

          <section className="rounded-bento border border-rule bg-card">
            {list.length === 0 && <p className="p-6 text-[13.5px] text-ink-muted">No tasks yet. Choose New task to ask for a scan.</p>}
            <ul>
              {list.map((t) => (
                <li key={t.id}>
                  <button onClick={() => setSel(t)} className="group flex min-h-[44px] w-full items-center gap-4 border-b border-rule px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-panel">
                    <span className="flex w-[150px] flex-none items-center gap-2">
                      <span className="h-2.5 w-2.5 flex-none rounded-full" style={dotStyle(t.status)} />
                      <span className="text-[12px] text-ink-muted">{CLIENT_LABEL[t.status]}</span>
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15.5px] font-medium text-ink" title={t.target}>{bare(t.target)}{t.path}</span>
                      <span className="mt-0.5 block truncate text-[12px] text-ink-muted">Until {localTime(t.not_after)} · {t.scan_mode === 'cloud' ? 'Cloud scan' : 'Local scan'}</span>
                    </span>
                    <span className="mono hidden flex-none text-[12px] text-ink-muted sm:block">{when(t.when)}</span>
                    <span className="grid h-8 w-8 flex-none place-items-center rounded-full border border-rule text-ink-muted opacity-0 transition-opacity duration-200 group-hover:text-ink group-hover:opacity-100"><ArrowUpRight size={15} /></span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
      <NewTaskDrawer open={open} onOpenChange={setOpen} onCreated={reload} />

      <Drawer open={!!sel} onOpenChange={(v) => !v && setSel(null)}>
        {sel && (
          <DrawerContent>
            <div className="border-b border-rule p-6">
              <span className="inline-flex items-center gap-2 rounded-pill bg-panel px-[11px] py-1.5 text-[12px] font-semibold text-ink-muted">
                <span className="h-2 w-2 rounded-full" style={dotStyle(sel.status)} />
                {CLIENT_LABEL[sel.status]}
              </span>
              <DrawerTitle className="mt-2.5 break-all text-[22px] font-bold tracking-[-0.02em] text-ink">{sel.target}{sel.path}</DrawerTitle>
              <p className="mt-1 text-[13px] text-ink-muted">Time limit {localTime(sel.not_before)} to {localTime(sel.not_after)}</p>
            </div>
            <div className="flex-1 space-y-5 p-6">
              <div className="rounded-input border border-rule bg-panel p-4 text-[13.5px] leading-relaxed text-ink">{CLIENT_HINT[sel.status]}</div>
              {sel.status === 'scheduled' && sel.scheduled_at && <p className="text-[13.5px] text-ink">Starts {localTime(sel.scheduled_at)}</p>}
              {sel.status === 'scanning' && sel.job_id && (
                <div className="rounded-input border border-rule bg-panel p-4"><ScanProgress jobId={sel.job_id} /></div>
              )}
              {sel.status === 'declined' && sel.reason && (
                <div className="rounded-input border border-crit-bg bg-crit-bg p-4 text-[13.5px] leading-relaxed text-crit">{sel.reason}</div>
              )}
              <section>
                <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">Timeline</h4>
                <ol className="space-y-3 border-l border-rule pl-4">
                  {timeline.map((i) => (
                    <li key={i.at + i.status} className="relative">
                      <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full" style={dotStyle(i.status)} />
                      <div className="text-[13.5px] font-semibold text-ink">{CLIENT_LABEL[i.status]}</div>
                      <div className="text-[12px] text-ink-muted">{localTime(i.at)}</div>
                      {i.note && <div className="mt-1 text-[13px] text-ink">{i.note}</div>}
                    </li>
                  ))}
                </ol>
              </section>
              {[['Scan runs', sel.scan_mode === 'cloud' ? 'By Varuna (cloud)' : 'On your computer'], ['Port', sel.port ? String(sel.port) : 'Default'], ['Notes', sel.notes || '-']].map(([l, v]) => (
                <div key={l} className="flex items-start justify-between gap-4 border-b border-rule pb-3 last:border-b-0">
                  <span className="text-[13px] text-ink-muted">{l}</span>
                  <b className="text-right text-[13.5px] font-semibold text-ink">{v}</b>
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
    </ClientPage>
  )
}
