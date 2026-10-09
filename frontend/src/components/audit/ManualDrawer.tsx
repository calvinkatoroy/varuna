import { useId, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { EMPTY_MANUAL, auditApi, manualProblem, type ManualForm } from '@/lib/audit'
import { SEVS, SEV_LABEL } from '@/lib/findings'
import { toast } from '@/lib/toast'

const field = 'mt-1 min-h-[44px] w-full rounded-input border border-rule bg-panel px-3 text-[13px] text-ink outline-none focus:border-accent'
const area = 'mt-1 w-full resize-y rounded-input border border-rule bg-panel px-3 py-2.5 text-[13px] text-ink outline-none focus:border-accent'

export function ManualDrawer({ tid, open, onOpenChange, onAdded, onCloseAutoFocus }: {
  tid: string; open: boolean; onOpenChange: (v: boolean) => void; onAdded: () => void; onCloseAutoFocus?: (e: Event) => void
}) {
  const [f, setF] = useState<ManualForm>(EMPTY_MANUAL)
  const [busy, setBusy] = useState(false)
  const set = (k: keyof ManualForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setF((p) => ({ ...p, [k]: e.target.value }))
  const [touched, setTouched] = useState<Record<string, boolean>>({})   // a message shows after the field was left, or after Add
  const [tried, setTried] = useState(false)
  const refs = useRef<Record<string, HTMLInputElement | HTMLTextAreaElement | null>>({})
  const uid = useId()
  const problem = manualProblem(f)
  const leave = (k: string) => () => setTouched((t) => ({ ...t, [k]: true }))
  const msg = (k: string) => (problem && problem.field === k && (tried || touched[k]) ? problem.msg : null)
  const err = (k: string) => `${uid}-${k}-err`
  const bad = (k: string) => ({ 'aria-invalid': msg(k) ? true : undefined, 'aria-describedby': msg(k) ? err(k) : undefined, onBlur: leave(k) })
  const note = (k: string) => msg(k) && <span id={err(k)} className="mt-1 block text-[12.5px] text-crit-ink">{msg(k)}</span>
  const submit = async () => {
    if (busy) return
    if (problem) { setTried(true); refs.current[problem.field]?.focus(); return }
    setBusy(true)
    try { await auditApi.addManual(tid, f); toast('Finding added'); setF(EMPTY_MANUAL); setTouched({}); setTried(false); onOpenChange(false); onAdded() }
    catch {} finally { setBusy(false) }
  }
  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent onCloseAutoFocus={onCloseAutoFocus}>
        <div className="border-b border-rule p-6 pr-16">
          <DrawerTitle className="text-[20px] font-bold tracking-[-0.02em] text-ink">Add a finding</DrawerTitle>
          <p className="mt-1 text-[13px] text-ink-muted">For something you found by hand. It counts as confirmed and goes into the report.</p>
        </div>
        <div className="flex-1 space-y-4 p-6">
          <label className="block text-[12.5px] text-ink-muted">Name
            <input ref={(el) => { refs.current.name = el }} value={f.name} maxLength={300} onChange={set('name')} className={field} {...bad('name')} />
            {note('name')}
          </label>
          <label className="block text-[12.5px] text-ink-muted">Severity
            <select value={f.severity} onChange={set('severity')} className={field}>
              {SEVS.map((s) => <option key={s} value={s}>{SEV_LABEL[s]}</option>)}
            </select>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-[12.5px] text-ink-muted">Host (blank = the task's host)
              <input value={f.host} maxLength={300} onChange={set('host')} className={field} />
            </label>
            <label className="block text-[12.5px] text-ink-muted">URL or parameter
              <input ref={(el) => { refs.current.url = el }} value={f.url} maxLength={2048} onChange={set('url')} className={field} {...bad('url')} />
              {note('url')}
            </label>
          </div>
          <label className="block text-[12.5px] text-ink-muted">What you found
            <textarea ref={(el) => { refs.current.description = el }} rows={4} maxLength={4000} value={f.description} onChange={set('description')} className={area} {...bad('description')} />
            {note('description')}
          </label>
          <label className="block text-[12.5px] text-ink-muted">Evidence (shown as written)
            <textarea rows={4} maxLength={6000} value={f.evidence} onChange={set('evidence')} className={`${area} font-mono text-[12px]`} />
          </label>
          <label className="block text-[12.5px] text-ink-muted">Impact
            <textarea rows={3} maxLength={4000} value={f.impact} onChange={set('impact')} className={area} />
          </label>
          <label className="block text-[12.5px] text-ink-muted">Remediation
            <textarea rows={3} maxLength={4000} value={f.remediation} onChange={set('remediation')} className={area} />
          </label>
        </div>
        <div className="sticky bottom-0 border-t border-rule bg-card p-6">
          <Button size="lg" className="w-full" disabled={busy} onClick={submit}>Add finding</Button>
        </div>
      </DrawerContent>
    </Drawer>
  )
}
