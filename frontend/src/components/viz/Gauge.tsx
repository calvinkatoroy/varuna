import { useEffect, useRef } from 'react'
import anime from 'animejs'

const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

// Semicircular resolution gauge (the CyberGuard speedometer idea): a ticked scanner arc that
// fills to `value`, with the figure counting up. The one signature data-viz on the page.
export function Gauge({ value, label, tone = 'low', size = 208 }: { value: number; label: string; tone?: string; size?: number }) {
  const arcRef = useRef<SVGPathElement>(null)
  const numRef = useRef<SVGTextElement>(null)
  const cx = 100, cy = 104, r = 82, ticks = 44
  const arc = `M ${cx - r},${cy} A ${r},${r} 0 0 1 ${cx + r},${cy}`

  useEffect(() => {
    if (reduced()) {
      arcRef.current?.setAttribute('stroke-dasharray', `${value} 100`)
      if (numRef.current) numRef.current.textContent = `${value}%`
      return
    }
    const o = { v: 0 }
    anime({
      targets: o, v: value, duration: 1150, easing: 'easeOutExpo',
      update: () => {
        arcRef.current?.setAttribute('stroke-dasharray', `${o.v} 100`)
        if (numRef.current) numRef.current.textContent = `${Math.round(o.v)}%`
      },
    })
  }, [value])

  return (
    <svg viewBox="0 0 200 118" width={size} height={size * 0.59} className="overflow-visible">
      {Array.from({ length: ticks + 1 }).map((_, i) => {
        const t = i / ticks
        const a = Math.PI * (1 - t)
        const ri = r + 5, ro = r + 12
        const on = t <= value / 100
        return (
          <line
            key={i}
            x1={cx + Math.cos(a) * ri} y1={cy - Math.sin(a) * ri}
            x2={cx + Math.cos(a) * ro} y2={cy - Math.sin(a) * ro}
            stroke={on ? `var(--color-${tone})` : 'var(--color-rule)'}
            strokeWidth={on ? 1.7 : 1} strokeLinecap="round"
          />
        )
      })}
      <path d={arc} pathLength={100} fill="none" stroke="var(--color-rule)" strokeWidth="9" strokeLinecap="round" />
      <path ref={arcRef} d={arc} pathLength={100} fill="none" stroke={`var(--color-${tone})`} strokeWidth="9" strokeLinecap="round" strokeDasharray="0 100" />
      <text ref={numRef} x={cx} y={cy - 12} textAnchor="middle" className="fill-ink font-display" style={{ fontSize: 36, fontWeight: 700, letterSpacing: '-0.02em' }}>0%</text>
      <text x={cx} y={cy + 6} textAnchor="middle" className="font-display" style={{ fontSize: 10.5, letterSpacing: '0.14em', fill: 'var(--color-ink-muted)' }}>{label.toUpperCase()}</text>
    </svg>
  )
}
