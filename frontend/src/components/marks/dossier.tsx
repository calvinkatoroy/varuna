import { useEffect, useRef } from 'react'
import { stampIn } from '@/lib/motion'

// Shared SVG filter that roughens edges so the stamp reads as hand-pressed ink, not a CSS
// border. Render once per page (top of the dossier).
export function DossierDefs() {
  return (
    <svg width="0" height="0" aria-hidden style={{ position: 'absolute' }}>
      <filter id="dossier-roughen" x="-10%" y="-10%" width="120%" height="120%">
        <feTurbulence type="fractalNoise" baseFrequency="0.018 0.028" numOctaves="2" seed="7" result="n" />
        <feDisplacementMap in="SourceGraphic" in2="n" scale="2.4" xChannelSelector="R" yChannelSelector="G" />
      </filter>
    </svg>
  )
}

// An inked rubber stamp: double-ruled frame + letter-spaced serif caps, tilted and roughened.
// `tone` is a severity/accent token name; the ink colour comes from that token.
export function VerdictStamp({
  label, tone = 'crit', tilt = -7, size = 'md', delay = 280, animate = true,
}: { label: string; tone?: string; tilt?: number; size?: 'sm' | 'md'; delay?: number; animate?: boolean }) {
  const ref = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (animate) stampIn(ref.current, delay)
    else if (ref.current) ref.current.style.opacity = '1'
  }, [animate, delay])
  const pad = size === 'sm' ? 'px-2 py-[3px] text-[10px] tracking-[0.16em]' : 'px-2.5 py-1 text-[12px] tracking-[0.2em]'
  return (
    <span className="inline-block" style={{ transform: `rotate(${tilt}deg)` }}>
      <span
        ref={ref}
        className={`pointer-events-none inline-flex select-none items-center rounded-[5px] border-[2.5px] font-serif font-semibold uppercase ${pad}`}
        style={{
          color: `var(--color-${tone})`,
          borderColor: 'currentColor',
          boxShadow: 'inset 0 0 0 1.5px currentColor',
          filter: 'url(#dossier-roughen)',
          opacity: 0,
        }}
      >
        {label}
      </span>
    </span>
  )
}

// Hand-drawn severity tally: 1–4 slightly-wobbled ink strokes, coloured by severity.
const weight: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 }
export function SeverityTally({ severity }: { severity: string }) {
  const w = weight[severity] ?? 1
  const width = 6 + w * 7
  return (
    <svg width={width} height="24" viewBox={`0 0 ${width} 24`} aria-hidden style={{ color: `var(--color-${severity})` }} className="flex-none">
      {Array.from({ length: w }).map((_, i) => {
        const x = 5 + i * 7
        const lean = i % 2 ? 1 : -1
        return <path key={i} d={`M ${x} 3 q ${lean * 1.1} 9 0 18`} stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" fill="none" />
      })}
    </svg>
  )
}
