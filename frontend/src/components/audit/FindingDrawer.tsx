import { useEffect, useState } from 'react'
import { Bug, FlaskConical } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Drawer, DrawerContent, DrawerTitle } from '@/components/ui/drawer'
import { auditApi } from '@/lib/audit'
import { SEVS, SEV_CHIP, SEV_LABEL, sevOf, type FindingRow } from '@/lib/findings'
import { invalidate } from '@/lib/swr'
import { toast } from '@/lib/toast'
import { useFindingDetail } from '@/lib/useFindingDetail'

const field = 'mt-1 min-h-[44px] w-full rounded-input border border-rule bg-panel px-3 text-[13px] text-ink outline-none focus:border-accent disabled:opacity-60'
const area = 'mt-1 w-full resize-y rounded-input border border-rule bg-panel px-3 py-2.5 text-[13px] text-ink outline-none focus:border-accent disabled:opacity-60'

export function FindingDrawer({ f, open, onOpenChange, tid, canAudit, onChanged }: {
  f: FindingRow | null; open: boolean; onOpenChange: (v: boolean) => void; tid: string; canAudit: boolean; onChanged: () => void
}) {
  const { detail, failed } = useFindingDetail('prv', open && f ? f.id : null)
  const [verdict, setVerdict] = useState<'tp' | 'fp'>('tp')
  const [severity, setSeverity] = useState('info')
  const [impact, setImpact] = useState('')
  const [remediation, setRemediation] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { if (f) { setVerdict(f.verdict); setSeverity(sevOf(f.severity)) } }, [f?.id])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (detail) { setImpact(detail.impact ?? ''); setRemediation(detail.remediation ?? ''); setVerdict(detail.verdict) } }, [detail?.id])   // eslint-disable-line react-hooks/exhaustive-deps
  if (!f) return null

  const pick = async (v: 'tp' | 'fp') => {
    if (v === verdict || busy || !canAudit) return
    const before = verdict
    setVerdict(v); setBusy(true)
    try { await auditApi.verdict(f.id, v); invalidate(`prv:/api/findings/id/${f.id}`); onChanged() }
    catch { setVerdict(before) }   // api.ts already toasted the reason
    finally { setBusy(false) }
  }
  const save = async () => {
    if (!detail || busy) return
    const body: Record<string, string> = {}
    if (severity !== sevOf(f.severity)) body.severity = severity
    if (impact !== (detail.impact ?? '')) body.impact = impact
    if (remediation !== (detail.remediation ?? '')) body.remediation = remediation
    if (!Object.keys(body).length) { toast('Nothing to save'); return }
    setBusy(true)
    try { await auditApi.edit(tid, f.id, body); invalidate(`prv:/api/findings/id/${f.id}`); toast('Saved'); onChanged(); onOpenChange(false) }
    catch {} finally { setBusy(false) }
  }
  const tone = (on: boolean, good: boolean) => on ? (good ? 'border-low bg-low-bg text-low-ink' : 'border-ink bg-panel text-ink') : 'border-rule text-ink-muted hover:text-ink'

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <div className="border-b border-rule p-6 pr-16">
          <span className={`inline-flex rounded-md px-2 py-1 text-[12px] font-bold ${SEV_CHIP[sevOf(f.severity)]}`}>{SEV_LABEL[sevOf(f.severity)]}</span>
          <DrawerTitle className="mt-2.5 text-[21px] font-bold tracking-[-0.02em] text-ink">{f.name}</DrawerTitle>
          <div className="mono mt-1 break-all text-[13px] text-ink-muted">{f.url || f.host}</div>
          <div className="mt-1 text-[12.5px] text-ink-faint">{f.tool === 'manual' ? 'Added by hand' : f.tool} · {f.cve ?? f.cwe ?? '-'}</div>
        </div>
        <div className="flex-1 space-y-6 p-6">
          <section>
            <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">Verdict</h4>
            <div className="grid grid-cols-2 gap-2">
              <button disabled={!canAudit || busy} onClick={() => pick('tp')} aria-pressed={verdict === 'tp'} className={`flex min-h-[44px] items-center justify-center gap-2 rounded-input border px-3 text-[13px] font-semibold disabled:opacity-60 ${tone(verdict === 'tp', true)}`}><Bug size={15} /> True positive</button>
              <button disabled={!canAudit || busy} onClick={() => pick('fp')} aria-pressed={verdict === 'fp'} className={`flex min-h-[44px] items-center justify-center gap-2 rounded-input border px-3 text-[13px] font-semibold disabled:opacity-60 ${tone(verdict === 'fp', false)}`}><FlaskConical size={15} /> False positive</button>
            </div>
            <p className="mt-2 text-[12px] text-ink-muted">A false positive is left out of the report. The change is logged.</p>
          </section>
          <section>
            <h4 className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-ink-muted">Evidence</h4>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-input border border-rule bg-panel p-3 font-mono text-[12px] leading-relaxed text-ink">{detail ? detail.evidence || '-' : failed ? 'Could not load the details.' : 'Loading'}</pre>
          </section>
          <section className="space-y-3">
            <h4 className="text-[12px] font-semibold uppercase tracking-wide text-ink-muted">What the report says</h4>
            <label className="block text-[12.5px] text-ink-muted">Severity
              <select value={severity} disabled={!canAudit} onChange={(e) => setSeverity(e.target.value)} className={field}>
                {SEVS.map((s) => <option key={s} value={s}>{SEV_LABEL[s]}</option>)}
              </select>
            </label>
            <label className="block text-[12.5px] text-ink-muted">Impact
              <textarea rows={3} maxLength={4000} value={impact} disabled={!canAudit || !detail} onChange={(e) => setImpact(e.target.value)} className={area} />
            </label>
            <label className="block text-[12.5px] text-ink-muted">Remediation
              <textarea rows={4} maxLength={4000} value={remediation} disabled={!canAudit || !detail} onChange={(e) => setRemediation(e.target.value)} className={area} />
            </label>
          </section>
        </div>
        {canAudit && (
          <div className="sticky bottom-0 flex gap-2.5 border-t border-rule bg-card p-6">
            <Button size="lg" className="flex-1" disabled={busy || !detail} onClick={save}>Save changes</Button>
          </div>
        )}
      </DrawerContent>
    </Drawer>
  )
}
