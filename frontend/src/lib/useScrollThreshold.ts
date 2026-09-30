import { useCallback, useRef } from 'react'

// Toggles `className` on the element once scroll crosses `distance`px (with hysteresis so it
// doesn't flicker right at the boundary), instead of continuously scrubbing a value every
// scroll frame. Pair with a CSS transition on that class (see .hero-sticky/.fade-collapse in
// index.css) so the animating happens on the compositor/paint, not via repeated JS-driven style
// writes.
//
// This replaces BOTH the old continuous JS scrubbing (useHeroShrink/useScrollFade, deleted) AND
// the native `animation-timeline: scroll()` version that came after it. Scroll-driven CSS
// animations only avoid main-thread work for transform/opacity - the properties here (padding,
// max-height, margin) are layout properties, so the browser still has to run layout on every
// scroll tick to resolve them regardless of what drives the animation. A threshold class toggle
// makes that layout recalculation happen ONCE per crossing instead of continuously, which is
// what actually fixes the slow-scroll stutter (confirmed: switching *what* drove the animation
// didn't help, because the cost was never about JS vs CSS - it was continuous vs one-shot).
//
// Callback ref (not useRef+useEffect): a page behind an async loading gate can render a
// completely different tree on its first pass (no element to attach to yet). An effect keyed on
// a constant dep only runs once, sees a null ref, and never re-runs once the real element mounts.
export function useScrollThreshold<T extends HTMLElement>(distance: number, className: string, hysteresis = 15) {
  const cleanup = useRef<(() => void) | null>(null)
  return useCallback(
    (el: T | null) => {
      cleanup.current?.()
      cleanup.current = null
      if (!el) return
      let past = false
      const apply = () => {
        const y = window.scrollY
        if (!past && y > distance) { past = true; el.classList.add(className) }
        else if (past && y < distance - hysteresis) { past = false; el.classList.remove(className) }
      }
      apply()
      window.addEventListener('scroll', apply, { passive: true })
      cleanup.current = () => window.removeEventListener('scroll', apply)
    },
    [distance, className],
  )
}
