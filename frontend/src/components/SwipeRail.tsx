import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

export type RailHandle = { scrollToIndex: (i: number) => void }

// A horizontal strip that never shows a scrollbar. Instead it gives the hand something to hold:
// native momentum + scroll-snap, soft fades where more content continues, and a small arrow at
// each edge that only appears when there is more to reach (and nudges until first used).
// Arrow keys scroll it when focused, so it is not touch-only. `onActiveChange` reports which
// child sits at the leading edge, so a tab strip elsewhere can mirror the position.
export const SwipeRail = forwardRef<RailHandle, {
  children: React.ReactNode
  className?: string
  label: string
  snap?: boolean
  onActiveChange?: (index: number) => void
}>(function SwipeRail({ children, className, label, snap = true, onActiveChange }, ref) {
  const el = useRef<HTMLDivElement>(null)
  const [edge, setEdge] = useState({ start: false, end: false })
  const [used, setUsed] = useState(false)

  const measure = useCallback(() => {
    const n = el.current
    if (!n) return
    setEdge({ start: n.scrollLeft > 4, end: n.scrollLeft + n.clientWidth < n.scrollWidth - 4 })
    if (onActiveChange) {
      const kids = [...n.children] as HTMLElement[]
      const left = n.scrollLeft + 8
      let idx = 0
      kids.forEach((k, i) => { if (k.offsetLeft - n.offsetLeft <= left) idx = i })
      if (n.scrollLeft + n.clientWidth >= n.scrollWidth - 4) idx = kids.length - 1
      onActiveChange(idx)
    }
  }, [onActiveChange])

  useEffect(() => {
    measure()
    const n = el.current
    if (!n) return
    const ro = new ResizeObserver(measure)
    ro.observe(n)
    return () => ro.disconnect()
  }, [measure, children])

  useImperativeHandle(ref, () => ({
    scrollToIndex: (i: number) => {
      const k = el.current?.children[i] as HTMLElement | undefined
      if (k && el.current) el.current.scrollTo({ left: k.offsetLeft - el.current.offsetLeft, behavior: 'smooth' })
    },
  }), [])

  const by = (dir: 1 | -1) => {
    setUsed(true)
    const n = el.current
    if (n) n.scrollBy({ left: dir * n.clientWidth * 0.85, behavior: 'smooth' })
  }
  const mask = edge.start && edge.end ? 'rail-mask-both' : edge.start ? 'rail-mask-start' : edge.end ? 'rail-mask-end' : ''

  return (
    <div className="relative">
      <div
        ref={el}
        role="region"
        aria-label={label}
        tabIndex={0}
        onScroll={measure}
        onPointerDown={() => setUsed(true)}
        onKeyDown={(e) => { if (e.key === 'ArrowRight') { e.preventDefault(); by(1) } else if (e.key === 'ArrowLeft') { e.preventDefault(); by(-1) } }}
        className={cn('rail no-scrollbar flex overflow-x-auto focus:outline-none focus-visible:ring-2 focus-visible:ring-focus', snap && 'snap-x snap-mandatory', mask, className)}
      >
        {children}
      </div>
      {edge.start && (
        <button type="button" onClick={() => by(-1)} aria-label="Scroll back" className="absolute left-1 top-1/2 z-10 hidden h-11 w-11 -translate-y-1/2 place-items-center rounded-full border border-rule bg-card/95 text-ink shadow-lg transition-transform active:scale-95 md:grid">
          <ChevronLeft size={18} />
        </button>
      )}
      {edge.end && (
        <button type="button" onClick={() => by(1)} aria-label="Scroll forward" className="absolute right-1 top-1/2 z-10 hidden h-11 w-11 -translate-y-1/2 place-items-center rounded-full border border-rule bg-card/95 text-ink shadow-lg transition-transform active:scale-95 md:grid">
          <span className={used ? '' : 'rail-nudge'}><ChevronRight size={18} /></span>
        </button>
      )}
    </div>
  )
})
