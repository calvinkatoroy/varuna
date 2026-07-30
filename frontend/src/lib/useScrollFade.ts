import { useCallback, useRef } from 'react'

// Fades an element's opacity out over `distance`px of scroll. Opacity-only (no height/padding/
// margin touched), so this can't cause the overlap, runaway-margin, or reflow-flicker bugs the
// old shrinking-hero approach had - it doesn't affect layout at all.
//
// Callback ref (not useRef+useEffect): a page behind an async loading gate renders a completely
// different tree on its first pass (no element to attach to yet). An effect keyed on a constant
// dep only runs once, sees a null ref, and never re-runs once the real element mounts later.
export function useScrollFade<T extends HTMLElement>(distance = 100) {
  const cleanup = useRef<(() => void) | null>(null)
  return useCallback(
    (el: T | null) => {
      cleanup.current?.()
      cleanup.current = null
      if (!el) return
      let raf = 0
      const apply = () => {
        el.style.opacity = String(1 - Math.min(Math.max(window.scrollY / distance, 0), 1))
      }
      const onScroll = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(apply) }
      apply()
      window.addEventListener('scroll', onScroll, { passive: true })
      cleanup.current = () => { window.removeEventListener('scroll', onScroll); cancelAnimationFrame(raf) }
    },
    [distance],
  )
}
