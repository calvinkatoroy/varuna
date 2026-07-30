import { useCallback, useRef } from 'react'

// Sets --shrink (0->1 over `distance`px of scroll) on the element it's attached to, via rAF (no
// React re-render). Used ONLY by the hero card's own shrinking padding (.hero-sticky in
// index.css) - nothing below the hero is compensated for it; cards flow freely and simply move
// up as the hero's own occupied height shrinks, exactly like normal `position: sticky` content.
// Once the hero is fully shrunk it stays at a constant compact height forever, and further
// scroll just lets it cover content normally, like an ordinary sticky nav bar.
//
// Callback ref (not useRef+useEffect): a page behind an async loading gate can render a
// completely different tree on its first pass (no hero at all). An effect keyed on a constant
// dep only runs once, sees the ref as null, bails, and never runs again once the real hero
// finally mounts after data loads. A callback ref fires every time React attaches it to an
// actual DOM node, however many renders it took to get there.
export function useHeroShrink<T extends HTMLElement>(distance = 140) {
  const cleanup = useRef<(() => void) | null>(null)
  return useCallback(
    (el: T | null) => {
      cleanup.current?.()
      cleanup.current = null
      if (!el) return
      let raf = 0
      const apply = () => {
        el.style.setProperty('--shrink', String(Math.min(Math.max(window.scrollY / distance, 0), 1)))
      }
      const onScroll = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(apply) }
      apply()
      window.addEventListener('scroll', onScroll, { passive: true })
      cleanup.current = () => { window.removeEventListener('scroll', onScroll); cancelAnimationFrame(raf) }
    },
    [distance],
  )
}
