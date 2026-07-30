import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

// Packed severity bubbles: each severity is a circle sized by its count, clustered around the
// largest. Hover lifts + names it; click drills into Findings. Aggregate caption below.
const SEV = [
  { key: 'critical', label: 'Critical', tone: 'crit', dark: false },
  { key: 'high', label: 'High', tone: 'high', dark: false },
  { key: 'medium', label: 'Medium', tone: 'med', dark: true },
  { key: 'low', label: 'Low', tone: 'low', dark: true },
] as const

const R = (n: number) => 14 + 11 * Math.sqrt(Math.max(n, 0.5))

export function PostureBubbles({ posture }: { posture: Record<string, number> }) {
  const nav = useNavigate()
  const [hover, setHover] = useState<string | null>(null)

  const items = SEV.map((s) => ({ ...s, n: posture[s.key] ?? 0 })).sort((a, b) => b.n - a.n)
  const cx = 120, cy = 94
  const [big, ...rest] = items
  const pos: Record<string, { x: number; y: number; r: number }> = { [big.key]: { x: cx, y: cy, r: R(big.n) } }
  rest.forEach((s, i) => {
    const a = -Math.PI / 2 + i * ((2 * Math.PI) / rest.length)
    const d = R(big.n) + R(s.n) - 8
    pos[s.key] = { x: cx + Math.cos(a) * d, y: cy + Math.sin(a) * d, r: R(s.n) }
  })
  const active = SEV.find((s) => s.key === hover)

  return (
    <div className="flex flex-1 flex-col">
      <svg viewBox="0 0 240 190" className="w-full flex-1">
        {items.map((s, i) => {
          const p = pos[s.key]
          const on = hover === s.key
          return (
            <g key={s.key} className="bub-enter" style={{ animationDelay: `${i * 80}ms` }}>
              <g
                className="cursor-pointer"
                style={{ transformBox: 'fill-box', transformOrigin: 'center', transform: on ? 'scale(1.07)' : 'scale(1)', transition: 'transform .2s var(--ease-out)' }}
                onMouseEnter={() => setHover(s.key)}
                onMouseLeave={() => setHover(null)}
                onClick={() => nav('/findings')}
              >
                <circle cx={p.x} cy={p.y} r={p.r} fill={`var(--color-${s.tone})`} opacity={on ? 1 : 0.92} />
                <text x={p.x} y={p.y} textAnchor="middle" dominantBaseline="central" className="font-display" fill={s.dark ? '#12140F' : '#fff'} style={{ fontSize: p.r * 0.72, fontWeight: 700 }}>{s.n}</text>
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
