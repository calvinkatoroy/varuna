import { useCallback, useEffect, useRef, useState } from 'react'
import { Loader2, Sparkles } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { PROMPT_MAX, auditApi, canApplyTurn, readOnlyReason, promptBlockedReason, turnActive, type AiTurn, type AuditSummary } from '@/lib/audit'
import { when } from '@/lib/format'
import { toast } from '@/lib/toast'
import { usePoll } from '@/lib/usePoll'

export function AiChat({ tid, summary, onChanged }: { tid: string; summary: AuditSummary; onChanged: () => void }) {
  const [turns, setTurns] = useState<AiTurn[] | null>(null)
  const [prompt, setPrompt] = useState('')
  const [sending, setSending] = useState(false)
  const [working, setWorking] = useState<string | null>(null)   // the turn being applied or undone
  const inflight = useRef(false)
  const load = useCallback(() => auditApi.turns(tid).then(setTurns).catch(() => setTurns((t) => t ?? [])), [tid])
  useEffect(() => { load() }, [load, summary.content_version])   // eslint-disable-line react-hooks/exhaustive-deps

  const active = turns?.find(turnActive) ?? null
  usePoll(active?.id ?? null, () => auditApi.turn(tid, active!.id), (t) => !turnActive(t), (t) => {
    setTurns((all) => (all ?? []).map((x) => (x.id === t.id ? t : x)))
    if (!turnActive(t)) toast(t.status === 'ready' ? 'A suggestion is ready to review' : t.error || 'The assistant could not answer')
  })

  const why = promptBlockedReason(prompt, sending || !!active)
  const send = async () => {
    if (inflight.current || why) return   // one request at a time, however fast the clicks come
    inflight.current = true
    setSending(true)
    try {
      const r = await auditApi.ask(tid, prompt.trim())
      setTurns((all) => [...(all ?? []), r.turn])
      setPrompt('')
    } catch {} finally { inflight.current = false; setSending(false) }
  }
  const apply = async (t: AiTurn) => {
    if (working) return
    setWorking(t.id)
    try { const r = await auditApi.apply(tid, t.id, summary.content_version); toast(`Applied as report version ${r.version}`); onChanged() }
    catch {} finally { await load(); setWorking(null) }   // a 409 is already toasted by api.ts; refresh what is shown either way
  }
  const undo = async (t: AiTurn) => {
    if (working || t.applied_version == null) return
    setWorking(t.id)
    try { const r = await auditApi.restore(tid, t.applied_version - 1, summary.content_version); toast(`Restored as report version ${r.version}`); onChanged() }
    catch {} finally { await load(); setWorking(null) }
  }

  return (
    <section className="overflow-hidden rounded-bento-lg border border-rule bg-card" aria-label="Report assistant">
      <h2 className="flex items-center gap-2 border-b border-rule px-5 py-3 text-[15px] font-bold text-ink"><Sparkles size={16} className="text-accent-ink" /> Report assistant</h2>
      <p className="px-5 pt-4 text-[12.5px] leading-relaxed text-ink-muted">
        Ask for changes to the wording, for example "make the executive summary shorter". It runs on this server's own model and only
        reworks text. Findings, severities and counts stay as scanned. Nothing changes until you press Apply.
      </p>
      <ol className="max-h-[460px] space-y-4 overflow-y-auto p-5" aria-live="polite">
        {turns === null && <li className="text-[13px] text-ink-faint">Loading</li>}
        {turns?.length === 0 && <li className="text-[13px] text-ink-muted">No requests yet.</li>}
        {turns?.map((t) => {
          const blocked = canApplyTurn(t, summary.content_version, summary.can_audit)
          return (
            <li key={t.id}>
              <div className="ml-auto max-w-[94%] rounded-bento bg-panel px-3.5 py-2.5 text-[13px] text-ink">
                <div className="mb-0.5 text-[11.5px] text-ink-muted">{t.actor} · {when(t.created_at)}</div>
                {t.prompt}
              </div>
              <div className="mt-2 rounded-bento border border-rule px-3.5 py-3 text-[13px]">
                {turnActive(t) && <p role="status" className="flex items-center gap-2 text-ink-muted"><Loader2 size={14} className="animate-spin" /> Working on it. A local model can take up to a minute.</p>}
                {t.status === 'failed' && <p role="alert" className="text-crit">{t.error}</p>}
                {t.status === 'ready' && (
                  <>
                    <p className="font-semibold text-ink">{t.summary || 'Suggested changes'}</p>
                    {t.applied ? (
                      <p className="mt-2 text-ink-muted">Applied as report version {t.applied_version}.</p>
                    ) : t.diff.length === 0 ? (
                      <p className="mt-2 text-ink-muted">This suggestion makes no change.</p>
                    ) : (
                      <ul className="mt-2 space-y-3">
                        {t.diff.map((d, i) => (
                          <li key={i} className="rounded-input border border-rule bg-panel p-3">
                            <div className="mb-1.5 flex flex-wrap items-center gap-2 text-[12px] text-ink-muted">
                              <span className="font-semibold text-ink">{d.op === 'insert_after' ? 'Add' : d.op === 'remove' ? 'Remove' : 'Change'}</span>
                              <span>{d.where}</span>
                              {d.sanitized && <span className="rounded-md border border-rule px-1.5 py-0.5" title="Markup or links were removed from this text">cleaned</span>}
                            </div>
                            {d.before != null && <p className="text-ink-muted"><b>Before: </b><span className="line-through decoration-1">{d.before}</span></p>}
                            {d.after != null && <p className="mt-1 text-ink"><b>After: </b>{d.after}</p>}
                          </li>
                        ))}
                      </ul>
                    )}
                    {!t.applied && t.diff.length > 0 && (
                      <div className="mt-3">
                        <Button className="min-h-[44px]" disabled={!!blocked || !!working} onClick={() => apply(t)}>{working === t.id ? 'Applying' : 'Apply these changes'}</Button>
                        {blocked && <p className="mt-1.5 text-[12px] text-ink-muted">{blocked}</p>}
                      </div>
                    )}
                    {t.applied && summary.can_audit && t.applied_version === summary.content_version && (
                      <Button variant="outline" size="sm" className="mt-3 min-h-[44px] sm:min-h-0" disabled={!!working} onClick={() => undo(t)}>Undo this change</Button>
                    )}
                  </>
                )}
              </div>
            </li>
          )
        })}
      </ol>
      {summary.can_audit ? (
        <div className="border-t border-rule p-5">
          <label className="block text-[12.5px] text-ink-muted">Your request
            <textarea rows={3} disabled={sending || !!active} maxLength={PROMPT_MAX} value={prompt} onChange={(e) => setPrompt(e.target.value)}
              className="mt-1 w-full resize-y rounded-input border border-rule bg-panel px-3 py-2.5 text-[13px] text-ink outline-none focus:border-accent" />
          </label>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
            <span className="text-[12px] text-ink-muted">{prompt.length}/{PROMPT_MAX}{why && prompt.trim() ? ` · ${why}` : ''}</span>
            <Button className="min-h-[44px]" disabled={!!why} aria-busy={sending || !!active} onClick={send}>{sending || active ? 'Working' : 'Send'}</Button>
          </div>
        </div>
      ) : (
        <p className="border-t border-rule px-5 py-4 text-[12.5px] text-ink-muted">{readOnlyReason(summary)} You can still read the history.</p>
      )}
    </section>
  )
}
