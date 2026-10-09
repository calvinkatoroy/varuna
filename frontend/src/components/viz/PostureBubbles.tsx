import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { hierarchy, pack } from 'd3-hierarchy'
import { ShieldCheck } from 'lucide-react'

// Packed severity bubbles via d3 circle-packing: each severity is a circle sized by its count,
// packed without overlap. Hover lifts + names it; click drills into Findings.
const SEV = [
  { key: 'critical', label: 'Critical', tone: 'crit', dark: false },
  { key: 'high', label: 'High', tone: 'high', dark: false },
  { key: 'medium', label: 'Medium', tone: 'med', dark: true },
  { key: 'low', label: 'Low', tone: 'low', dark: true },
] as const

const W = 240, H = 200

export function PostureBubbles({ posture }: { posture: Record<string, number> }) {
  const nav = useNavigate()
  const [hover, setHover] = useState<string | null>(null)

  const nodes = useMemo(() => {
    const data = { children: SEV.map((s) => ({ ...s, value: Math.max(posture[s.key] ?? 0, 0.001) })) }
    const root = hierarchy<any>(data).sum((d) => d.value)
    const packed = pack<any>().size([W, H]).padding(6)(root)
    return packed.leaves()
  }, [posture])

  const active = SEV.find((s) => s.key === hover)
  const empty = SEV.every((s) => (posture[s.key] ?? 0) === 0)

  if (empty) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2.5 text-center">
        <span className="grid h-11 w-11 place-items-center rounded-full bg-low-bg text-low"><ShieldCheck size={22} /></span>
        <div className="text-[13.5px] font-semibold text-ink">No findings yet</div>
        <div className="text-[12px] text-ink-muted">Nothing found across your engagements so far.</div>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full flex-1">
        {nodes.map((n) => {
          const s = n.data
          const on = hover === s.key
          const count = posture[s.key] ?? 0
          return (
            <g key={s.key}>
              <g
                className="cursor-pointer"
                style={{ transformBox: 'fill-box', transformOrigin: 'center', transform: on ? 'scale(1.07)' : 'scale(1)', transition: 'transform .2s var(--ease-out)' }}
                onMouseEnter={() => setHover(s.key)}
                onMouseLeave={() => setHover(null)}
                onClick={() => nav('/findings')}
              >
                <circle cx={n.x} cy={n.y} r={n.r} fill={`var(--color-${s.tone})`} opacity={on ? 1 : 0.92} />
                <text x={n.x} y={n.y} textAnchor="middle" dominantBaseline="central" className="font-display" fill={s.dark ? '#12140F' : '#fff'} style={{ fontSize: Math.min(n.r * 0.7, 30), fontWeight: 700 }}>{count}</text>
              </g>
            </g>
          )
        })}
      </svg>
      <div className="mt-2 flex items-center justify-between text-[12.5px]">
        <span className="text-ink-muted">{active ? `${active.label} severity` : `${posture.open} open of ${posture.total}`}</span>
        <span className="font-semibold text-ink">{posture.resolved}% resolved</span>
      </div>
    </div>
  )
}
