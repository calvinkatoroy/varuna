import type { ReactNode } from 'react'

// The cockpit's outlined stat circle, lifted so the client sub-pages speak the same visual
// language as the Posture tile instead of regressing to plain tables.
const ring: Record<string, string> = {
  c: 'border-crit text-crit', h: 'border-high text-high', m: 'border-med text-med',
  l: 'border-low text-low', o: 'border-ink-faint text-ink-muted', s: 'border-accent text-accent',
}

export function StatRing({ tone, icon, n, unit, label }: { tone: string; icon: ReactNode; n: number | string; unit?: string; label: string }) {
  return (
    <div className="flex items-center gap-3.5">
      <span className={`grid h-[46px] w-[46px] flex-none place-items-center rounded-full border-[1.5px] ${ring[tone]}`}>{icon}</span>
      <div>
        <div className="text-[23px] font-bold leading-none tracking-[-0.02em] text-ink">
          {n}{unit && <small className="ml-0.5 text-[13px] font-semibold text-ink-faint">{unit}</small>}
        </div>
        <div className="mt-[5px] text-[12px] text-ink-muted">{label}</div>
      </div>
    </div>
  )
}
