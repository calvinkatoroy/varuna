import { useCallback, useRef } from 'react'

// Sets --fade (0->1 over `distance`px of scroll) on the element it's attached to, via rAF (no
// React re-render). Paired with the .fade-collapse CSS class, which uses --fade to drive BOTH
// opacity AND max-height/margin down to 0 - opacity alone isn't enough: an invisible element
// still reserves its full layout box, so the hero card it lives in could never shrink below
// "topbar height + this row's natural height" no matter how much its own padding collapsed.
//
// Callback ref (not useRef+useEffect): a page behind an async loading gate can render a
// completely different tree on its first pass (no element to attach to yet). An effect keyed on
// a constant dep only runs once, sees a null ref, and never re-runs once the real element mounts.
export function useScrollFade<T extends HTMLElement>(distance = 100) {
  const cleanup = useRef<(() => void) | null>(null)
  return useCallback(
    (el: T | null) => {
      cleanup.current?.()
      cleanup.current = null
      if (!el) return
      let raf = 0
      const apply = () => {
        el.style.setProperty('--fade', String(Math.min(Math.max(window.scrollY / distance, 0), 1)))
      }
      const onScroll = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(apply) }
      apply()
      window.addEventListener('scroll', onScroll, { passive: true })
      cleanup.current = () => { window.removeEventListener('scroll', onScroll); cancelAnimationFrame(raf) }
    },
    [distance],
  )
}
