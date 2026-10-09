import { useId, useRef, useState } from 'react'
import { Check, Download, Eye, EyeOff, Lock, ShieldCheck } from 'lucide-react'
import { api, download as downloadFile } from '@/api'
import { Button } from '@/components/ui/button'
import { ClientPage } from '@/components/ClientPage'
import { ErrorRetry } from '@/components/ErrorRetry'
import { useApiData } from '@/lib/useApiData'
import { FEEDS } from '@/lib/feeds'
import { maskPw } from '@/lib/audit'
import { bare, when } from '@/lib/format'
import { copyText, selectText } from '@/lib/clipboard'

type Report = { id: string; engagement: string; delivered: string; findings: number; templates: string[]; signed: boolean; filename?: string }
const chip = 'rounded-md border border-rule bg-panel px-2 py-1 text-[12px] text-ink-muted'

// The password never changes for a report (the same one opens every future version), so it can be shown again
// whenever the client needs it (GET /api/reports/{id}/password). It is masked by default, kept only in memory
// (never in the URL, storage or logs) and gone when the page is left.
function Password({ id }: { id: string }) {
  const [pw, setPw] = useState<string | null>(null)
  const [shown, setShown] = useState(false)
  const [copied, setCopied] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const code = useRef<HTMLElement>(null)
  const label = useId()
  const getting = useRef(false)
  if (pw !== null) {
    const copy = async () => {
      setMsg(null)
      if (await copyText(pw)) { setCopied(true); setTimeout(() => setCopied(false), 1600); return }
      setShown(true)   // the dots cannot be copied by hand: show the text and select it
      setMsg('Copying did not work here. The password is selected: press Ctrl+C.')
      requestAnimationFrame(() => selectText(code.current))
    }
    return (
      <span className="flex min-h-[44px] flex-wrap items-center gap-x-3 gap-y-1">
        <span role="group" aria-labelledby={label} className="flex items-center">
          <span id={label} className="sr-only">{shown ? 'Password' : 'Password, hidden'}</span>
          <code ref={code} className="mono select-all rounded-md bg-panel px-2.5 py-1.5 text-[13px] font-medium text-accent-ink">{maskPw(pw, shown)}</code>
        </span>
        <button type="button" onClick={() => setShown((v) => !v)} aria-pressed={shown} className="flex min-h-[44px] items-center gap-1.5 rounded-md px-2 text-[12.5px] font-semibold text-ink-muted hover:text-ink">
          {shown ? <><EyeOff size={14} /> Hide</> : <><Eye size={14} /> Show</>}
        </button>
        <button type="button" onClick={copy} className="min-h-[44px] rounded-md px-2 text-[12.5px] font-semibold text-ink-muted hover:text-ink">{copied ? 'Copied' : 'Copy'}</button>
        {msg && <span role="alert" className="w-full text-[12.5px] text-crit-ink">{msg}</span>}
        <span className="w-full text-[12px] text-ink-faint">The same password for every version of this report. Keep it separate from the file.</span>
      </span>
    )
  }
  return (
    <span className="flex flex-col items-center">
      <button
        onClick={() => {
          if (getting.current) return
          getting.current = true
          setMsg(null)
          api.qget(`/api/reports/${id}/password`).then((r) => { setPw(r.password); setShown(true) })
            .catch(() => setMsg('Could not get the password. Try again.')).finally(() => { getting.current = false })
        }}
        className="flex min-h-[44px] items-center gap-2 rounded-md px-1 text-[13px] font-medium text-ink-muted transition-colors hover:text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        title="Shows the password for this report. It stays the same every time."
      >
        <Lock size={14} /> Show password
      </button>
      {msg && <span role="alert" className="text-[12.5px] text-crit-ink">{msg}</span>}
    </span>
  )
}

export default function ClientReports() {
  const { data: rows, error, reload } = useApiData<Report[]>(FEEDS.reports.load, FEEDS.reports.key)

  const [got, setGot] = useState<Record<string, boolean>>({})
  // Only marks "Downloaded" once the file actually came back - downloadFile() throws on
  // failure (report not delivered yet, file missing), which used to leave the button showing
  // a checkmark for a download that never happened.
  const download = (r: Report) => {
    downloadFile(api.publicBase, `/api/reports/${r.id}/delivered`, r.filename || `${r.id}.pdf`)
      .then(() => setGot((g) => ({ ...g, [r.id]: true })))
      .catch(() => {})
  }
  const featured = rows?.[0]
  const rest = rows?.slice(1) ?? []

  return (
    <ClientPage title="Reports" sub="Signed deliverables. Each PDF is read only. Its password stays the same, so you can show it again any time.">
      {error ? (
        <ErrorRetry message={error} onRetry={reload} />
      ) : !rows ? (
        <div className="p-10 text-ink-faint">Loading</div>
      ) : (
        <div className="flex flex-col gap-3">
          {featured && (
            <section className="grid grid-cols-1 gap-6 rounded-bento border border-rule bg-card p-6 lg:grid-cols-[1.5fr_1fr]">
              <div className="min-w-0">
                <span className="text-[12px] font-medium uppercase tracking-[0.12em] text-accent-ink">Latest report</span>
                <h2 className="mt-2 text-[clamp(22px,3vw,30px)] font-bold leading-tight tracking-[-0.02em] text-ink">{bare(featured.engagement)}</h2>
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[13px] text-ink-muted">
                  <span>Delivered {when(featured.delivered)}</span>
                  <span>{featured.findings} findings</span>
                  {featured.signed && <span className="flex items-center gap-1.5 text-low"><ShieldCheck size={14} /> Governance signed</span>}
                </div>
                {featured.filename && <p className="mono mt-3 break-all text-[12px] text-ink-faint">{featured.filename}</p>}
                <div className="mt-5 flex flex-wrap gap-1.5">
                  {featured.templates.map((t) => <span key={t} className={chip}>{t}</span>)}
                </div>
              </div>
              <div className="flex flex-col justify-center gap-3 border-t border-rule pt-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
                <Button size="lg" className="w-full" onClick={() => download(featured)}>{got[featured.id] ? <><Check size={17} /> Downloaded</> : <><Download size={17} /> Download protected PDF</>}</Button>
                <div className="flex justify-center"><Password id={featured.id} /></div>
                <p className="text-center text-[12px] leading-relaxed text-ink-faint">The password is not inside the file. It is the same every time you open this report.</p>
              </div>
            </section>
          )}

          {rest.length > 0 && (
            <section className="rounded-bento border border-rule bg-card">
              <ul>
                {rest.map((r) => (
                  <li key={r.id}>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-rule px-4 py-3 last:border-b-0 sm:px-5 sm:py-4">
                      <div className="min-w-0 basis-full sm:basis-0 sm:flex-1">
                        <b className="block break-words text-[15px] font-medium leading-snug text-ink sm:truncate">{bare(r.engagement)}</b>
                        <span className="text-[12px] text-ink-faint">{when(r.delivered)}, {r.findings} findings</span>
                      </div>
                      <Password id={r.id} />
                      <Button variant="outline" size="sm" className="ml-auto min-h-[44px] sm:min-h-0" onClick={() => download(r)}>{got[r.id] ? <><Check size={15} /> Got it</> : <><Download size={15} /> PDF</>}</Button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </ClientPage>
  )
}
