import { AlertTriangle, RotateCcw } from 'lucide-react'

// Shared "this page failed to load" state - a real, reachable path once the app talks to a
// real (fallible) backend instead of a mock that never errors. Full-width block matching each
// page's own "Loading..." placeholder so the layout doesn't jump between the two.
export function ErrorRetry({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="col-span-full flex flex-col items-center gap-3 p-10 text-center">
      <span className="grid h-11 w-11 place-items-center rounded-full bg-crit-bg text-crit"><AlertTriangle size={20} /></span>
      <div className="text-[13.5px] text-ink-muted">{message}</div>
      <button onClick={onRetry} className="flex items-center gap-1.5 rounded-pill border border-rule px-3.5 py-1.5 text-[12.5px] font-semibold text-ink transition-colors hover:bg-panel">
        <RotateCcw size={13} /> Retry
      </button>
    </div>
  )
}
