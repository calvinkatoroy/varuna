import { useEffect, useState } from 'react'
import { Check, Loader2, Pause, X } from 'lucide-react'
import { api, streamEvents } from '@/api'

const STEPS: [string, string][] = [['katana', 'Crawling'], ['nuclei', 'Scanning'], ['sqlmap', 'Testing injection']]

type Frame = { status: string; per_tool_status: Record<string, string>; suspended?: boolean }

// Installer-style live scan progress (v2, SSE): a stepped indicator, not a smooth percentage -
// the agent only ever reports at tool-phase boundaries (before Katana/Nuclei/SQLMap each
// start), never fractional progress within one, so a byte-level progress bar isn't honest
// here. This is the same "Extracting... Configuring... Finishing..." pattern any installer
// uses when it only knows discrete stages, not bytes transferred.
//
// Connects on mount via a raw fetch+ReadableStream reader (api.ts's streamEvents - native
// EventSource can't send the Authorization header this app needs), cleans up on unmount. If
// the stream never connects, falls back to whatever `initial` snapshot the caller already had
// (e.g. the board's last-known per_tool_status) - degraded but not blank.
export function ScanProgress({ jobId, base = api.publicBase, initial }: { jobId: string; base?: string; initial?: Frame }) {
  const [frame, setFrame] = useState<Frame | undefined>(initial)

  useEffect(() => {
    setFrame(initial)
    return streamEvents(base, `/api/scans/${jobId}/events`, (data) => setFrame(data))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId, base])

  const per = frame?.per_tool_status ?? {}
  const terminal = frame?.status === 'done' || frame?.status === 'failed'
  const doneCount = STEPS.filter(([tool]) => per[tool] === 'done').length
  const pct = Math.round((doneCount / STEPS.length) * 100)

  return (
    <div className="flex flex-col gap-3">
      <div className="relative h-1 overflow-hidden rounded-full bg-rule">
        <div className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />
      </div>
      <ul className="flex flex-col gap-2">
        {STEPS.map(([tool, label]) => {
          const state = per[tool] ?? (terminal ? 'skipped' : 'pending')
          const active = state === 'running'
          return (
            <li key={tool} className="flex items-center gap-2.5 text-[13px]">
              <span className={`grid h-6 w-6 flex-none place-items-center rounded-full ${
                state === 'done' ? 'bg-low-bg text-low'
                  : state === 'failed' ? 'bg-crit-bg text-crit'
                  : active ? 'bg-accent-soft text-accent-ink'
                  : 'bg-panel text-ink-faint'
              }`}>
                {state === 'done' && <Check size={13} />}
                {state === 'failed' && <X size={13} />}
                {active && (frame?.suspended ? <Pause size={12} /> : <Loader2 size={13} className="animate-spin" />)}
                {(state === 'pending' || state === 'skipped') && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
              </span>
              <span className={state === 'skipped' ? 'text-ink-faint line-through' : active ? 'font-semibold text-ink' : 'text-ink-muted'}>
                {label}{active && frame?.suspended ? ' - suspended' : ''}
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
