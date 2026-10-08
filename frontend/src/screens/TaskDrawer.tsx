import { useEffect, useRef, useState } from 'react'
import { Download, Upload, Activity, SlidersHorizontal, KeyRound } from 'lucide-react'
import { api, ApiError, download, team, upload, type BoardCard, type TaskAction, type TaskDetail, type TaskEvent } from '@/api'
import { useAuth } from '@/auth'
import { Button } from '@/components/ui/button'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { ScanProgress } from '@/components/ScanProgress'
import { AdvancedScanDrawer, toApiOpts } from './AdvancedScanDrawer'
import { TZ_LABEL, localTime, toLocalInput, toUtcIso } from '@/lib/format'
import { toast } from '@/lib/toast'

export const KIND_LABEL: Record<string, string> = {
  claim: 'Claim', decline: 'Decline', start: 'Start now', schedule: 'Schedule', unschedule: 'Cancel schedule',
  suspend: 'Suspend', resume: 'Resume now', close: 'Close as expired', submit: 'Submit for review',
  approve: 'Approve', send_back: 'Send back', deliver: 'Approve and deliver',
}
export const STAGE_LABEL: Record<string, string> = {
  task: 'Task', 'scan/pending': 'Scan pending', 'scan/scheduled': 'Scheduled', 'scan/in_progress': 'Scanning',
  'scan/suspended': 'Suspended', completed: 'Completed', review_lead_pentester: 'Lead Pentester review',
  review_lead_cyber: 'Lead Cybersecurity review', review_governance: 'Governance review', review_manager: 'Manager review',
  delivering: 'Delivering', delivered: 'Delivered', declined: 'Declined', expired: 'Expired',
}
// Moves that cannot be taken back take two taps (the first arms the button and says so).
const CONSEQUENTIAL = new Set(['decline', 'approve', 'send_back', 'deliver', 'close', 'suspend'])
const key = (stage: string, s: string | null) => (stage === 'scan' && s ? `scan/${s}` : stage)
const ta = 'w-full resize-none rounded-input border border-rule bg-panel px-3.5 py-3 text-[13px] text-ink placeholder:text-ink-muted outline-none focus:border-accent'
const field = 'mt-1 min-h-[44px] w-full rounded-input border border-rule bg-panel px-3 text-[13px] text-ink outline-none focus:border-accent'

export function TaskDrawer({ card, open, onOpenChange, onMoved }: { card: BoardCard | null; open: boolean; onOpenChange: (v: boolean) => void; onMoved: () => void }) {
  const { user } = useAuth()
  const [detail, setDetail] = useState<TaskDetail | null>(null)
  const [events, setEvents] = useState<TaskEvent[]>([])
  const [comment, setComment] = useState('')
  const [at, setAt] = useState('')
  const [minutes, setMinutes] = useState('240')
  const [opts, setOpts] = useState<Record<string, unknown> | undefined>()
  const [optsOpen, setOptsOpen] = useState(false)
  const [armed, setArmed] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [templates, setTemplates] = useState<string[]>([])
  const [tpl, setTpl] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const reload = () => {
    if (!card) return
    team.detail(card.id).then((d) => { setDetail(d); setAt(d.task.scheduled_at ? toLocalInput(d.task.scheduled_at) : toLocalInput(d.task.not_before)) }).catch(() => setDetail(null))
    team.events(card.id).then(setEvents).catch(() => setEvents([]))
  }
  useEffect(() => { setComment(''); setOpts(undefined); setArmed(null); setDetail(null); setEvents([]); reload() }, [card?.id])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { api.pget('/api/templates').then(setTemplates).catch(() => {}) }, [])
  useEffect(() => { if (!armed) return; const t = setTimeout(() => setArmed(null), 8000); return () => clearTimeout(t) }, [armed])

  if (!card) return null
  const actions = card.actions
  const needsComment = actions.some((a) => a.comment && a.allowed)
  const needsSchedule = actions.some((a) => a.kind === 'schedule' && a.allowed)
  const canStart = actions.some((a) => (a.kind === 'start' || a.kind === 'resume') && a.allowed)
  const review = card.stage === 'completed' || card.stage.startsWith('review_')

  const reasonFor = (a: TaskAction): string | null => {
    if (!a.allowed) return a.why
    if (a.comment && !comment.trim()) return 'Write a reason first'
    if (a.kind === 'schedule' && !at) return 'Choose a start time'
    return null
  }
  const run = async (a: TaskAction) => {
    if (CONSEQUENTIAL.has(a.kind) && armed !== a.to) { setArmed(a.to); return }
    setArmed(null); setBusy(true)
    const n = minutes ? Number(minutes) : undefined
    try {
      await team.move(card.id, {
        to: a.to, version: card.version,
        ...(a.comment ? { comment: comment.trim() } : {}),
        ...(a.kind === 'schedule' ? { scheduled_at: toUtcIso(at), max_minutes: n } : {}),
        ...(a.kind === 'start' || a.kind === 'resume' ? { max_minutes: n } : {}),
        ...((a.kind === 'start' || a.kind === 'resume' || a.kind === 'schedule') && opts ? { opts } : {}),
      })
      toast(`${KIND_LABEL[a.kind] ?? a.kind}: done.`)
      onOpenChange(false)
    } catch (e) {
      // api.ts already toasted the server's reason (422 = what to fix). 409 means someone else moved it
      // first: say so plainly; the board refetches below either way.
      if (e instanceof ApiError && e.status === 409) { toast('Someone else already handled this. Refreshing the board.'); onOpenChange(false) }
    } finally {
      setBusy(false); onMoved()
    }
  }
  const onPickFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]; e.target.value = ''
    if (!f || !detail?.report_id) return
    try { await upload(api.privateBase, `/api/pipeline/reports/${detail.report_id}/version?note=${encodeURIComponent('Uploaded ' + f.name)}`, f); toast('New version uploaded.'); reload() } catch {}
  }
  const regenerate = async () => {
    if (!tpl || !detail?.report_id) return
    try { await api.ppost(`/api/pipeline/reports/${detail.report_id}/template`, { template: tpl }); toast(`Regenerated as ${tpl}.`); reload() } catch {}
  }
  const reissue = async () => {
    if (!detail?.report_id) return
    try { await api.ppost(`/api/pipeline/reports/${detail.report_id}/reissue-password`); toast(`New view-once password issued for ${card.client}.`) } catch {}
  }

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <div className="border-b border-rule p-6 pr-16">
          <span className="text-[12px] font-medium text-ink-muted">{card.scanMode === 'cloud' ? 'Cloud scan' : 'Local scan'} · {STAGE_LABEL[key(card.stage, card.scanState)] ?? card.stage}{card.assignee ? ` · ${card.assignee}` : ''}</span>
          <DrawerTitle className="mt-1 text-[20px] font-bold tracking-[-0.02em] text-ink">{card.client}</DrawerTitle>
          <div className="mono break-all text-[13px] text-ink-muted">{card.target}</div>
        </div>
        <div className="flex-1 space-y-6 p-6">
          {detail && (
            <section className="grid grid-cols-2 gap-3 text-[13px]">
              <div><div className="text-ink-muted">Client time limit</div><div className="font-semibold text-ink">{localTime(detail.task.not_before)} to {localTime(detail.task.not_after)}</div></div>
              <div><div className="text-ink-muted">Max duration</div><div className="font-semibold text-ink">{detail.task.max_minutes ? `${detail.task.max_minutes} min` : '-'}</div></div>
              <div className="col-span-2"><div className="text-ink-muted">Notes</div><div className="whitespace-pre-wrap font-semibold text-ink">{detail.task.notes || '-'}</div></div>
              {card.reason && <div className="col-span-2"><div className="text-ink-muted">Reason</div><div className="font-semibold text-ink">{card.reason}</div></div>}
            </section>
          )}
          {card.scanState === 'in_progress' && card.jobId && (
            <section className="rounded-input border border-rule bg-panel p-4"><ScanProgress jobId={card.jobId} base={api.privateBase} /></section>
          )}
          {review && detail?.report_id && (
            <section>
              <div className="mb-2.5 flex items-center justify-between">
                <h4 className="text-[12px] font-semibold uppercase tracking-wide text-ink-muted">Versions</h4>
                <input ref={fileRef} type="file" accept=".docx" aria-label="Upload a new report version" className="hidden" onChange={onPickFile} />
                <button onClick={() => fileRef.current?.click()} className="flex min-h-[44px] items-center gap-1.5 text-[12.5px] font-semibold text-accent-ink"><Upload size={14} /> Upload new</button>
              </div>
              <div className="mb-3 flex items-center gap-2">
                <select value={tpl} onChange={(e) => setTpl(e.target.value)} aria-label="Report template" className="min-h-[44px] min-w-0 flex-1 rounded-input border border-rule bg-panel px-3 text-[13px] text-ink">
                  <option value="">Regenerate as template…</option>
                  {templates.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <Button variant="outline" onClick={regenerate} disabled={!tpl} className="min-h-[44px]">Regenerate</Button>
              </div>
              <ul className="space-y-2">
                {detail.versions.map((v) => (
                  <li key={v.version_no} className="flex items-center gap-3 rounded-input border border-rule bg-panel p-3">
                    <span className="grid h-8 w-8 flex-none place-items-center rounded-lg bg-card text-[12px] font-bold text-ink">v{v.version_no}</span>
                    <div className="min-w-0 flex-1"><div className="truncate text-[13px] font-medium text-ink">{v.note}</div><div className="text-[12px] text-ink-muted">{v.editor} · {localTime(v.created_at.replace(' ', 'T') + 'Z')}</div></div>
                    <button onClick={() => download(api.privateBase, `/api/pipeline/reports/${detail.report_id}/versions/${v.version_no}/download`, `${detail.report_id}_v${v.version_no}.docx`)} aria-label={`Download version ${v.version_no}`} className="grid h-11 w-11 flex-none place-items-center rounded-full text-ink-muted hover:bg-card hover:text-ink"><Download size={16} /></button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {card.stage === 'delivered' && user?.role === 'governance' && detail?.report_id && (
            <button onClick={reissue} className="flex min-h-[44px] items-center gap-2 text-[13px] font-semibold text-accent-ink"><KeyRound size={15} /> Re-issue the view-once password</button>
          )}
          <section>
            <h4 className="mb-2.5 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">History</h4>
            <ol className="space-y-2.5">
              {events.map((e) => (
                <li key={e.id} className="text-[13px]">
                  <span className="font-semibold text-ink">{STAGE_LABEL[key(e.to_stage, e.to_scan_state)] ?? e.to_stage ?? ''}</span>
                  <span className="text-ink-muted"> · {e.actor} · {localTime(e.at)}</span>
                  {e.comment && <div className="mt-0.5 text-ink">{e.comment}</div>}
                </li>
              ))}
              {events.length === 0 && <li className="text-[13px] text-ink-muted">No history yet.</li>}
            </ol>
          </section>
          {needsSchedule && (
            <section className="grid gap-3 sm:grid-cols-2">
              <label className="text-[12.5px] text-ink-muted">Start ({TZ_LABEL})
                <input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} className={field} />
              </label>
              <label className="text-[12.5px] text-ink-muted">Max duration (minutes)
                <input type="number" min={1} inputMode="numeric" value={minutes} onChange={(e) => setMinutes(e.target.value)} className={field} />
              </label>
              {detail && <p className="text-[12.5px] text-ink-muted sm:col-span-2">The client allows scanning from {localTime(detail.task.not_before)} to {localTime(detail.task.not_after)}.</p>}
            </section>
          )}
          {canStart && !needsSchedule && (
            <label className="block text-[12.5px] text-ink-muted">Max duration (minutes)
              <input type="number" min={1} inputMode="numeric" value={minutes} onChange={(e) => setMinutes(e.target.value)} className={field} />
            </label>
          )}
          {(canStart || needsSchedule) && (
            <button onClick={() => setOptsOpen(true)} className="flex min-h-[44px] items-center gap-2 text-[13px] font-semibold text-accent-ink">
              <SlidersHorizontal size={15} /> {opts ? 'Scan options set (change)' : 'Scan options (optional)'}
            </button>
          )}
          {needsComment && (
            <label className="block text-[12.5px] text-ink-muted">Reason (required for decline, suspend, close and send back; a decline reason is shown to the client)
              <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} className={`${ta} mt-1`} />
            </label>
          )}
          {card.scanState === 'in_progress' && !card.jobId && (
            <div className="flex items-center gap-3 rounded-input border border-rule bg-panel p-4 text-[13px] text-ink"><Activity size={18} className="text-info" /> Waiting for the job to be created.</div>
          )}
        </div>
        <div className="sticky bottom-0 flex flex-wrap gap-2.5 border-t border-rule bg-card p-6">
          {actions.length === 0 && <p className="text-[13px] text-ink-muted">Nothing to do here for your role.</p>}
          {actions.map((a) => {
            const why = reasonFor(a)
            return (
              <div key={a.to} className="flex min-w-[140px] flex-1 flex-col gap-1">
                <Button size="lg" variant={a.kind === 'send_back' || a.kind === 'decline' || a.kind === 'unschedule' ? 'outline' : 'default'}
                  disabled={!!why || busy} title={why ?? undefined} onClick={() => run(a)}>
                  {armed === a.to ? `Tap again: ${KIND_LABEL[a.kind] ?? a.kind}` : KIND_LABEL[a.kind] ?? a.kind}
                </Button>
                {why && <span className="text-[12px] text-ink-muted">{why}</span>}
              </div>
            )
          })}
        </div>
        <AdvancedScanDrawer key={card.id} open={optsOpen} onOpenChange={setOptsOpen} fixedTarget={card.target} actionLabel="Use these options"
          onLaunch={(o) => setOpts(toApiOpts(o))} />
      </DrawerContent>
    </Drawer>
  )
}
