import { useCallback, useRef } from 'react'

// Drives the sticky-shrink hero: as the page scrolls, sets --shrink (0->1) on the hero element
// via rAF (no React re-render). CSS (see .hero-sticky in index.css) uses the variable to shrink
// the hero's height and fade its title as it pins to the top.
//
// Implemented as a CALLBACK ref (not useRef+useEffect): a page that shows a "Loading..." gate
// before its data arrives renders a completely different tree on its first pass (no header at
// all). An effect keyed on a constant dep (e.g. [distance]) only runs on that first render, sees
// ref.current === null, bails, and never runs again once the real header finally mounts after
// data loads - the scroll listener never attaches. A callback ref fires every time React attaches
// the ref to an actual DOM node, however many renders it took to get there, so this can't happen.
export function useHeroShrink<T extends HTMLElement>(distance = 140) {
  const cleanup = useRef<(() => void) | null>(null)
  return useCallback(
    (el: T | null) => {
      cleanup.current?.()
      cleanup.current = null
      if (!el) return
      let raf = 0
      const apply = () => {
        const p = Math.min(Math.max(window.scrollY / distance, 0), 1)
        el.style.setProperty('--shrink', String(p))
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
