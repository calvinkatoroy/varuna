import { useCallback, useRef } from 'react'

// Drives the sticky-shrink hero. Sets two CSS vars on the wrapping element (via rAF, no React
// re-render): --shrink (0->1 over `distance`px, used by .hero-sticky to shrink height/fade the
// title) and --over (0+, px scrolled PAST `distance`).
//
// --over exists because position:sticky, on its own, guarantees the gap between the stuck
// header and whatever follows it in normal flow shrinks 1:1 with scroll and eventually hits
// zero (then overlaps) - that's true no matter how the header itself shrinks, since the header
// shrinking and the content behind it scrolling up are two independent things once the header
// is pinned. Content that wants a PERSISTENT gap needs to grow its own top margin by exactly
// however much scroll happened past the shrink point, canceling that consumption. See
// `.content-offset` in index.css, applied to the row of tiles below the hero.
//
// Implemented as a callback ref (not useRef+useEffect): a page that shows a "Loading..." gate
// before its data arrives renders a completely different tree on its first pass (no hero at
// all). An effect keyed on a constant dep only runs on that first render, sees the ref as null,
// bails, and never runs again once the real hero finally mounts after data loads - the scroll
// listener never attaches. A callback ref fires every time React attaches it to an actual DOM
// node, however many renders it took to get there.
export function useHeroShrink<T extends HTMLElement>(distance = 140) {
  const cleanup = useRef<(() => void) | null>(null)
  return useCallback(
    (el: T | null) => {
      cleanup.current?.()
      cleanup.current = null
      if (!el) return
      let raf = 0
      const apply = () => {
        const y = window.scrollY
        el.style.setProperty('--shrink', String(Math.min(Math.max(y / distance, 0), 1)))
        el.style.setProperty('--over', String(Math.max(y - distance, 0)))
      }
      const onScroll = () => {
        cancelAnimationFrame(raf)
        raf = requestAnimationFrame(apply)
      }
      apply()
      window.addEventListener('scroll', onScroll, { passive: true })
      cleanup.current = () => { window.removeEventListener('scroll', onScroll); cancelAnimationFrame(raf) }
    },
    [distance],
  )
}
