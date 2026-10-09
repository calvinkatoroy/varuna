import { useId, useRef, useState } from 'react'
import { Copy, Download, Eye, EyeOff, FileText, KeyRound, Loader2, TriangleAlert } from 'lucide-react'
import { ApiError } from '@/api'
import { Button } from '@/components/ui/button'
import { PDF_POLL_MAX_MS, PDF_STEPS, auditApi, generateBlockedReason, isPdfActive, maskPw, pdfStale, pdfStep, type AuditSummary, type PdfJob } from '@/lib/audit'
import { when } from '@/lib/format'
import { copyText, selectText } from '@/lib/clipboard'
import { toast } from '@/lib/toast'
import { usePoll } from '@/lib/usePoll'

export function PdfPanel({ tid, summary, onChanged }: { tid: string; summary: AuditSummary; onChanged: () => void }) {
  const [starting, setStarting] = useState(false)
  const [job, setJob] = useState<PdfJob | null>(null)   // the job this page last heard about
  const [timedOut, setTimedOut] = useState(false)       // we stopped watching; the server may still be building
  const [err, setErr] = useState<string | null>(null)   // why the last Generate click was refused (429, 409, network)
  const [pw, setPw] = useState<string | null>(null)     // kept in memory only, gone when the page closes
  const [pwShown, setPwShown] = useState(false)
  const [pwErr, setPwErr] = useState<string | null>(null)
  const inflight = useRef(false)
  const revealing = useRef(false)   // one click = one password_view row in the audit trail
  const code = useRef<HTMLElement>(null)
  const pwLabel = useId()
  const shown = job ?? summary.pdf.active
  const watched = !timedOut && shown && isPdfActive(shown.status) ? shown : null
  const busy = starting || !!watched
  const canAudit = summary.can_audit
  const blocked = generateBlockedReason(summary, busy)
  const ready = summary.pdf.history.filter((j) => j.status === 'ready')
  const stale = pdfStale(summary.pdf)

  usePoll(watched?.id ?? null, () => auditApi.job(tid, watched!.id), (j) => !isPdfActive(j.status), (j) => {
    setJob(j)
    if (!isPdfActive(j.status)) { if (j.status === 'ready') toast(`PDF ready: ${j.filename}`); onChanged() }   // a failure shows in the inline alert
  }, { maxMs: PDF_POLL_MAX_MS, onTimeout: () => setTimedOut(true) })

  const start = async () => {
    if (blocked || inflight.current) return   // aria-disabled keeps focus on the button, so the guard lives here   // ten fast clicks: only the first one starts anything
    inflight.current = true
    setStarting(true)
    setErr(null)
    setTimedOut(false)
    try {
      const r = await auditApi.generate(tid)
      setJob(r.job)
      if (!isPdfActive(r.job.status)) onChanged()   // an up-to-date PDF came back, nothing was built
    } catch (e: any) {
      setErr(e instanceof ApiError ? e.message : 'Could not start the PDF. Check your connection.')   // the server's own words, e.g. the rate-limit message on 429
    } finally { inflight.current = false; setStarting(false) }
  }
  const recheck = () => { setTimedOut(false); onChanged() }
  const reveal = async () => {
    if (revealing.current) return
    revealing.current = true
    setPwErr(null)
    try { setPw((await auditApi.password(tid)).password); setPwShown(true) }
    catch (e: any) { setPwErr(e instanceof ApiError ? e.message : 'Could not get the password. Try again.') }
    finally { revealing.current = false }
  }
  const copy = async () => {
    setPwErr(null)
    if (await copyText(pw ?? '')) return
    setPwShown(true)   // the dots cannot be copied by hand: show the text and select it
    setPwErr('Copying did not work here. The password is selected: press Ctrl+C.')
    requestAnimationFrame(() => selectText(code.current))
  }

  const live = watched ? PDF_STEPS[pdfStep(watched.status)]
    : timedOut ? 'The PDF is taking longer than expected.'
    : shown?.status === 'ready' ? `PDF ready: ${shown.filename ?? ''}` : ''

  return (
    <section className="overflow-hidden rounded-bento-lg border border-rule bg-card" aria-label="PDF report">
      <h2 className="border-b border-rule px-5 py-3 text-[15px] font-bold text-ink">PDF report</h2>
      <div className="space-y-4 p-5">
        {/* Always mounted so screen readers announce every change of step. */}
        <p role="status" aria-live="polite" className="sr-only">{live}</p>

        {stale && canAudit && (
          <div className="flex gap-2.5 rounded-input border border-rule bg-med-bg p-3.5 text-[12.5px] text-med-ink">
            <TriangleAlert size={16} className="mt-0.5 flex-none" aria-hidden="true" />
            <p><b>The report changed after the last PDF was made.</b> Generate a new PDF. Until then the task cannot be submitted for review.</p>
          </div>
        )}

        {canAudit && (
          <div>
            <Button size="lg" className="w-full aria-disabled:pointer-events-none aria-disabled:opacity-50" aria-disabled={!!blocked} aria-busy={busy} onClick={start}>
              {busy ? <><Loader2 size={17} className="animate-spin" /> Preparing the PDF</> : summary.pdf.latest ? 'Generate a new PDF' : 'Generate the PDF'}
            </Button>
            {blocked && !busy && <p className="mt-2 text-[12.5px] text-ink-muted">{blocked}</p>}
            {err && <p role="alert" className="mt-2 text-[12.5px] text-crit-ink">{err}</p>}
          </div>
        )}

        {watched && (
          <div className="rounded-input border border-rule bg-panel p-3.5">
            <div className="text-[13px] font-semibold text-ink">{PDF_STEPS[pdfStep(watched.status)]}</div>
            <ol className="mt-2 grid grid-cols-3 gap-1.5" aria-hidden="true">
              {PDF_STEPS.slice(0, 3).map((s, i) => <li key={s} className={`h-1.5 rounded-full ${i <= pdfStep(watched.status) ? 'bg-accent' : 'bg-rule'}`} />)}
            </ol>
            <p className="mt-2 text-[12px] text-ink-muted">This can take a minute. You can leave this page; the PDF keeps building.</p>
          </div>
        )}
        {timedOut && (
          <div className="rounded-input border border-rule bg-panel p-3.5 text-[12.5px] text-ink">
            <p>This is taking longer than expected. The PDF may still finish in the background.</p>
            <button onClick={recheck} className="mt-1 min-h-[44px] font-semibold text-accent-ink">Check again</button>
          </div>
        )}
        {shown?.status === 'failed' && <p role="alert" className="text-[12.5px] text-crit-ink">{shown.error || 'PDF generation failed.'} Nothing was lost; the earlier PDF is still there.</p>}

        <ul className="space-y-2">
          {ready.map((j, i) => (
            <li key={j.id} className="flex items-center gap-3 rounded-input border border-rule p-3">
              <FileText size={18} className="flex-none text-ink-muted" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <div className="break-all text-[13px] font-medium text-ink">{j.filename}</div>
                <div className="text-[12px] text-ink-muted">PDF {j.n} · report v{j.content_version} · {when(j.updated_at)}{i === 0 && summary.pdf.current ? ' · up to date' : ''}</div>
              </div>
              <button onClick={() => auditApi.downloadPdf(tid, j).catch(() => {})} aria-label={`Download ${j.filename}`} className="grid h-11 w-11 flex-none place-items-center rounded-full text-ink-muted hover:bg-panel hover:text-ink"><Download size={16} /></button>
            </li>
          ))}
          {ready.length === 0 && <li className="text-[13px] text-ink-muted">No PDF has been generated yet.</li>}
        </ul>

        {ready.length > 0 && (
          <div>
            {pw !== null ? (
              <div className="flex flex-wrap items-center gap-3">
                <span role="group" aria-labelledby={pwLabel} className="flex items-center">
                  <span id={pwLabel} className="sr-only">{pwShown ? 'PDF password' : 'PDF password, hidden'}</span>
                  <code ref={code} className="mono select-all rounded-md bg-panel px-2.5 py-1.5 text-[13px] text-accent-ink">{maskPw(pw, pwShown)}</code>
                </span>
                <button onClick={() => setPwShown((v) => !v)} aria-pressed={pwShown} className="flex min-h-[44px] items-center gap-1.5 px-2 text-[12.5px] font-semibold text-ink-muted hover:text-ink">
                  {pwShown ? <><EyeOff size={14} /> Hide</> : <><Eye size={14} /> Show</>}
                </button>
                <button onClick={copy} className="flex min-h-[44px] items-center gap-1.5 px-2 text-[12.5px] font-semibold text-ink-muted hover:text-ink"><Copy size={14} /> Copy</button>
                {pwErr && <span role="alert" className="w-full text-[12.5px] text-crit-ink">{pwErr}</span>}
                <span className="w-full text-[12px] text-ink-muted">The same password opens every PDF of this report, now and in future versions. It is the one the client gets.</span>
              </div>
            ) : (
              <>
                <button onClick={reveal} className="flex min-h-[44px] items-center gap-2 text-[13px] font-semibold text-accent-ink"><KeyRound size={15} /> Show the PDF password</button>
                {pwErr && <p role="alert" className="text-[12.5px] text-crit-ink">{pwErr}</p>}
              </>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
