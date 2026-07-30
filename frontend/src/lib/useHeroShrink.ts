import { useEffect, useRef } from 'react'

// Drives the sticky-shrink hero: as the page scrolls, sets --shrink (0->1) on the hero element
// via rAF (no React re-render). CSS (see .hero-sticky in index.css) uses the variable to shrink
// the hero's height and fade its title as it pins to the top. Also keeps the nav pill's viewport
// position stable while scrolled, which is most of why the page-transition jump happened.
export function useHeroShrink<T extends HTMLElement>(distance = 140) {
  const ref = useRef<T>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    let raf = 0
    const onScroll = () => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const p = Math.min(Math.max(window.scrollY / distance, 0), 1)
        el.style.setProperty('--shrink', String(p))
      })
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => { window.removeEventListener('scroll', onScroll); cancelAnimationFrame(raf) }
  }, [distance])
  return ref
}
