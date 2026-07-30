import { useCallback, useRef } from 'react'

// Toggles a `.is-faded` class once scroll crosses `distance`px (with a little hysteresis so it
// doesn't flicker right at the boundary), instead of scrubbing opacity/height continuously every
// scroll frame. The row's own CSS transition (see .fade-collapse) then animates it out over a
// fixed, short duration.
//
// This used to set a CSS var every rAF tick while scrolling, which changes max-height - a layout
// property - on every frame. That's cheap on its own, but the row contains a button with a
// plain CSS backdrop-blur (glassmorphism, not our SVG liquid glass): forcing that blur to
// reflow/repaint 60 times a second while scrolling is what caused the visible stutter. A class
// toggle fires at most twice per scroll session (crossing the threshold each direction), so the
// reflow happens once, not continuously.
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
      const hysteresis = 15
      let faded = false
      const apply = () => {
        const y = window.scrollY
        if (!faded && y > distance) { faded = true; el.classList.add('is-faded') }
        else if (faded && y < distance - hysteresis) { faded = false; el.classList.remove('is-faded') }
      }
      apply()
      window.addEventListener('scroll', apply, { passive: true })
      cleanup.current = () => window.removeEventListener('scroll', apply)
    },
    [distance],
  )
}
