import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { NewTask } from '@/api'
import { TZ_LABEL, toLocalInput, toUtcIso } from '@/lib/format'

const field = 'w-full rounded-input border border-rule bg-panel px-3.5 py-3 text-[14px] text-ink placeholder:text-ink-faint outline-none transition-colors focus:border-accent'
const label = 'mb-1.5 block text-[12.5px] font-medium text-ink-muted'

// Does this look like an address only the client's own network can reach? (Cloud scans cannot.)
const looksPrivate = (t: string) => {
  const h = t.trim().replace(/^[a-z]+:\/\//i, '').split(/[/:?#]/)[0].toLowerCase()
  return !!h && (h === 'localhost' || !h.includes('.') || /\.(local|localhost|internal|lan|home|corp|intranet|test)$/.test(h) ||
    /^(127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.)/.test(h))
}

const inHours = (h: number) => toLocalInput(new Date(Date.now() + h * 3600_000).toISOString())

// The client's scan request: what to test and the time limit the scan must stay inside.
export function TaskForm({ onSubmit, submitLabel = 'Send task' }: { onSubmit: (t: NewTask) => Promise<void> | void; submitLabel?: string }) {
  const [scan, setScan] = useState<'local' | 'cloud'>('cloud')
  const [target, setTarget] = useState('')
  const [path, setPath] = useState('')
  const [port, setPort] = useState('')
  const [notes, setNotes] = useState('')
  const [from, setFrom] = useState(inHours(1))
  const [until, setUntil] = useState(inHours(73))
  const [busy, setBusy] = useState(false)

  const portOk = port === '' || (/^\d+$/.test(port) && +port >= 1 && +port <= 65535)
  const pathOk = path === '' || path.startsWith('/')
  const windowOk = !!from && !!until && new Date(from) < new Date(until) && new Date(until) > new Date()
  const blocked = scan === 'cloud' && looksPrivate(target)
  const ready = !!target.trim() && portOk && pathOk && windowOk && !blocked

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!ready) return
    setBusy(true)
    try {
      await onSubmit({ target: target.trim(), path: path.trim(), ...(port ? { port: +port } : {}), notes,
        not_before: toUtcIso(from), not_after: toUtcIso(until), scan_mode: scan })
    } catch {
      // api.ts already toasted the reason; this only un-sticks the button.
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <fieldset>
        <legend className={label}>Where should the scan run?</legend>
        <div role="radiogroup" className="grid gap-2 sm:grid-cols-2">
          {([
            ['cloud', 'By Varuna (cloud)', 'Nothing to install. Only for websites that are open on the internet.'],
            ['local', 'On my computer', 'You install a small program once. Needed for internal or private systems.'],
          ] as const).map(([v, title, text]) => (
            <label key={v} className={`flex min-h-[44px] cursor-pointer items-start gap-3 rounded-input border p-3 transition-colors ${scan === v ? 'border-accent bg-accent-soft/40' : 'border-rule bg-panel'}`}>
              <input type="radio" name="scan-mode" value={v} checked={scan === v} onChange={() => setScan(v)} className="mt-1 h-4 w-4 flex-none accent-[var(--color-accent)]" />
              <span><b className="block text-[13px] text-ink">{title}</b><span className="text-[12px] leading-snug text-ink-muted">{text}</span></span>
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label htmlFor="task-target" className={label}>Target</label>
        <input id="task-target" className={field} value={target} onChange={(e) => setTarget(e.target.value)} placeholder="https://portal.perusahaan.co.id" required />
        {blocked && (
          <p role="alert" className="mt-2 rounded-input bg-med-bg p-3 text-[12.5px] leading-relaxed text-ink">
            This looks like an internal address, which Varuna's cloud cannot reach.{' '}
            <button type="button" onClick={() => setScan('local')} className="min-h-[44px] font-semibold text-accent-ink underline">Scan on my computer instead</button>
          </p>
        )}
      </div>
      <div className="grid grid-cols-[1fr_120px] gap-3">
        <div>
          <label htmlFor="task-path" className={label}>Path <span className="text-ink-faint">(optional)</span></label>
          <input id="task-path" className={field} value={path} onChange={(e) => setPath(e.target.value)} placeholder="/app" aria-invalid={!pathOk} />
        </div>
        <div>
          <label htmlFor="task-port" className={label}>Port <span className="text-ink-faint">(optional)</span></label>
          <input id="task-port" className={field} inputMode="numeric" value={port} onChange={(e) => setPort(e.target.value)} placeholder="443" aria-invalid={!portOk} />
        </div>
      </div>
      {!pathOk && <p className="-mt-2 text-[12.5px] text-crit">The path starts with a slash, like /app.</p>}
      {!portOk && <p className="-mt-2 text-[12.5px] text-crit">The port is a number from 1 to 65535.</p>}
      <div>
        <label htmlFor="task-notes" className={label}>Notes <span className="text-ink-faint">(optional)</span></label>
        <textarea id="task-notes" rows={3} className={`${field} resize-none`} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Test account, pages to skip, who to call if something breaks" />
      </div>
      <fieldset>
        <legend className={label}>Time limit <span className="text-ink-faint">({TZ_LABEL})</span></legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="text-[12.5px] text-ink-muted">From
            <input type="datetime-local" className={`${field} mt-1`} value={from} onChange={(e) => setFrom(e.target.value)} required />
          </label>
          <label className="text-[12.5px] text-ink-muted">Until
            <input type="datetime-local" className={`${field} mt-1`} value={until} onChange={(e) => setUntil(e.target.value)} required />
          </label>
        </div>
        {!windowOk && <p className="mt-2 text-[12.5px] text-crit">The time limit must end after it starts, and in the future.</p>}
        <p className="mt-2 text-[12px] text-ink-muted">The scan only runs inside this window.</p>
      </fieldset>
      <Button type="submit" size="lg" className="w-full" disabled={!ready || busy}>{submitLabel} <ArrowRight size={16} /></Button>
    </form>
  )
}
