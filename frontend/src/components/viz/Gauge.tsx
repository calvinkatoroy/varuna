// Semicircular resolution gauge (the CyberGuard speedometer idea): a ticked scanner arc filled to `value`,
// with the figure. Drawn at its final value at once - a page that is revisited often should not replay it.
export function Gauge({ value, label, tone = 'low', size = 208 }: { value: number; label: string; tone?: string; size?: number }) {
  const cx = 100, cy = 104, r = 82, ticks = 44
  const arc = `M ${cx - r},${cy} A ${r},${r} 0 0 1 ${cx + r},${cy}`

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
      <path d={arc} pathLength={100} fill="none" stroke={`var(--color-${tone})`} strokeWidth="9" strokeLinecap="round" strokeDasharray={`${value} 100`} />
      <text x={cx} y={cy - 12} textAnchor="middle" className="fill-ink font-display" style={{ fontSize: 36, fontWeight: 700, letterSpacing: '-0.02em' }}>{value}%</text>
      <text x={cx} y={cy + 6} textAnchor="middle" className="font-display" style={{ fontSize: 10.5, letterSpacing: '0.14em', fill: 'var(--color-ink-muted)' }}>{label.toUpperCase()}</text>
    </svg>
  )
}
