import { useMemo, useState } from 'react'
import { Filter, ShieldCheck, Bug, FlaskConical, ChevronDown } from 'lucide-react'
import { api } from '@/api'
import { Button } from '@/components/ui/button'
import { ShellActions, ShellTitle } from '@/components/ShellSlots'
import { ErrorRetry } from '@/components/ErrorRetry'
import { TargetAccordion } from '@/components/findings/TargetAccordion'
import { TargetFindings } from '@/components/findings/TargetFindings'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { FEEDS } from '@/lib/feeds'
import { SEVS, SEV_CHIP, SEV_LABEL, patchRows, sevOf, type FindingRow, type TargetRow } from '@/lib/findings'
import { useApiData } from '@/lib/useApiData'
import { useFindingDetail } from '@/lib/useFindingDetail'
import { useFindingsUrl } from '@/lib/useFindingsUrl'
import { toast } from '@/lib/toast'

const clientOf = (t: TargetRow) => t.org_name ?? 'Internal'   // organization name from the server

export default function FindingsReview() {
  const { data: targets, error, reload, fresh } = useApiData<TargetRow[]>(FEEDS.teamTargets.load, FEEDS.teamTargets.key)
  const url = useFindingsUrl()
  const [sevFilter, setSevFilter] = useState<string | null>(null)
  const [sel, setSel] = useState<FindingRow | null>(null)
  const [open, setOpen] = useState(false)
  const { detail, failed } = useFindingDetail('prv', open && sel ? sel.id : null)

  // Clients come from the targets themselves (their organization), so the filter always matches.
  const clients = useMemo(() => [...new Set((targets ?? []).map(clientOf))].sort(), [targets])
  // Start on the client of the deep-linked target, else the first client. Chosen once: later changes belong to
  // the person using the dropdown. A stale cache may not know the linked target yet, so wait for a fresh load.
  const linked = targets?.find((t) => t.task_id === url.target)
  const waiting = !!url.target && !linked && !fresh
  const initial = !targets?.length || waiting ? '' : linked ? clientOf(linked) : clients[0]
  const [picked, setPicked] = useState('')
  const client = picked || initial   // cached targets show at once, without a flash of "no findings"
  const setClient = setPicked

  const shown = useMemo(() => (targets ?? []).filter((t) => clientOf(t) === client), [targets, client])
  const lost = !!url.target && !!targets && fresh && !targets.some((t) => t.task_id === url.target)
  const pickClient = (cl: string) => { setClient(cl); url.set({ target: null, finding: null }) }
  const openRow = (f: FindingRow) => { setSel(f); setOpen(true); url.set({ finding: f.id }) }

  const setVerdict = (f: FindingRow, v: 'tp' | 'fp') => {
    const prev = f.verdict
    patchRows('prv', f.task_id, f.id, { verdict: v })
    setSel((s) => (s && s.id === f.id ? { ...s, verdict: v } : s))
    api.ppost(`/api/findings/${f.id}/verdict`, { verdict: v }).then(() => reload()).catch(() => {
      patchRows('prv', f.task_id, f.id, { verdict: prev })
      setSel((s) => (s && s.id === f.id ? { ...s, verdict: prev } : s))
    })
  }
  const markFixed = (f: FindingRow) => {
    patchRows('prv', f.task_id, f.id, { status: 'fixed' })
    setSel((s) => (s && s.id === f.id ? { ...s, status: 'fixed' } : s))
    api.ppost(`/api/findings/${f.id}/status`, { status: 'fixed' }).then(
      () => { toast('Marked as fixed'); reload() },
      () => {
        patchRows('prv', f.task_id, f.id, { status: 'open' })
        setSel((s) => (s && s.id === f.id ? { ...s, status: 'open' } : s))
      },
    )
  }

  const filterBtn = 'flex h-11 items-center gap-2 rounded-pill bg-white/[.16] px-4 text-[13px] font-medium text-[#F2F5EF]'

  return (
    <>
      <ShellTitle size="band" title="Findings review" kicker={client || 'Loading…'} />
      <ShellActions>
        <DropdownMenu>
          <DropdownMenuTrigger className={filterBtn}>
            <Filter size={15} /> {client || 'Loading…'} <ChevronDown size={14} />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {clients.map((cl) => <DropdownMenuItem key={cl} onClick={() => pickClient(cl)}>{cl}</DropdownMenuItem>)}
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger className={`${filterBtn} capitalize`}>
            <Filter size={15} /> {sevFilter ?? 'All severities'} <ChevronDown size={14} />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={() => setSevFilter(null)}>All severities</DropdownMenuItem>
            <DropdownMenuSeparator />
            {SEVS.map((s) => <DropdownMenuItem key={s} onClick={() => setSevFilter(s)} className="capitalize">{s}</DropdownMenuItem>)}
          </DropdownMenuContent>
        </DropdownMenu>
      </ShellActions>

      {error ? (
        <ErrorRetry message={error} onRetry={reload} />
      ) : !targets ? (
        <div className="p-10 text-ink-faint">Loading…</div>
      ) : (
        <div className="mt-3.5 overflow-hidden rounded-bento-lg border border-rule bg-card">
          {lost && (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-5 py-4 text-[13.5px] text-ink">
              <span>That target was not found. It may have been removed.</span>
              <Button variant="outline" size="sm" className="min-h-[44px]" onClick={() => url.set({ target: null, finding: null })}>Show all targets</Button>
            </div>
          )}
          {shown.length === 0 && (client || fresh) && <div className="px-5 py-10 text-center text-[13px] text-ink-faint">No findings for {client || 'this client'}.</div>}
          <TargetAccordion
            targets={shown}
            openId={url.target}
            staff
            onToggle={(id) => url.set({ target: id, finding: null })}
            renderPanel={(t) => (
              <TargetFindings
                plane="prv"
                taskId={t.task_id}
                severity={sevFilter}
                focusId={url.finding}
                staff
                onOpen={openRow}
                onDismissFocus={() => url.set({ finding: null })}
              />
            )}
          />
        </div>
      )}

      <Drawer open={open} onOpenChange={setOpen}>
        {sel && (
          <DrawerContent>
            <div className="border-b border-rule p-6">
              <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] font-bold ${SEV_CHIP[sevOf(sel.severity)]}`} title={sevOf(sel.severity) === sel.severity ? undefined : sel.severity}>{SEV_LABEL[sevOf(sel.severity)]}</span>
              <DrawerTitle className="mt-2.5 text-[21px] font-bold tracking-[-0.02em] text-ink">{sel.name}</DrawerTitle>
              <div className="mono mt-1 text-[13px] text-ink-muted">{sel.url || sel.host}</div>
              <div className="mt-1 text-[12.5px] text-ink-faint">{sel.tool} · {sel.cve ?? sel.cwe ?? '-'}</div>
            </div>

            <div className="flex-1 space-y-6 p-6">
              <section>
                <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Verdict</h4>
                <div className="grid grid-cols-2 gap-2">
                  <VerdictBtn on={sel.verdict === 'tp'} icon={<Bug size={15} />} label="True positive" tone="low" onClick={() => setVerdict(sel, 'tp')} />
                  <VerdictBtn on={sel.verdict === 'fp'} icon={<FlaskConical size={15} />} label="False positive" tone="faint" onClick={() => setVerdict(sel, 'fp')} />
                </div>
              </section>
              <section>
                <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-faint">Evidence</h4>
                <pre className="overflow-x-auto rounded-input border border-rule bg-panel p-3 font-mono text-[12px] leading-relaxed text-ink">{detail ? detail.evidence : failed ? 'Could not load the details.' : 'Loading'}</pre>
              </section>
              <section>
                <h4 className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-ink-faint"><ShieldCheck size={13} className="text-accent-ink" /> AI remediation</h4>
                <p className="text-[13.5px] leading-relaxed text-ink">{detail ? detail.remediation ?? 'Not yet enriched.' : failed ? 'Could not load the details.' : 'Loading'}</p>
              </section>
            </div>

            <div className="sticky bottom-0 flex gap-2.5 border-t border-rule bg-card p-6">
              <Button variant="outline" size="lg" className="flex-1" disabled={sel.status === 'fixed'} onClick={() => markFixed(sel)}>{sel.status === 'fixed' ? 'Fixed' : 'Mark fixed'}</Button>
              <Button size="lg" className="flex-1" onClick={() => { toast('Review saved'); setOpen(false) }}>Save</Button>
            </div>
          </DrawerContent>
        )}
      </Drawer>
    </>
  )
}

function VerdictBtn({ on, icon, label, tone, onClick }: { on: boolean; icon: React.ReactNode; label: string; tone: string; onClick: () => void }) {
  return (
    <button onClick={onClick} className={`flex min-h-[44px] items-center justify-center gap-2 rounded-input border px-3 py-3 text-[13px] font-semibold transition-colors ${on ? (tone === 'low' ? 'border-low bg-low-bg text-low-ink' : 'border-ink bg-panel text-ink') : 'border-rule text-ink-muted hover:text-ink'}`}>
      {icon} {label}
    </button>
  )
}
