import { useEffect, useRef, type DependencyList } from 'react'
import { applyLiquidGlass, type GlassOpts } from './liquidGlass'

// Apply liquid glass to every element matching `selector` (e.g. '.glass-card'). Re-runs when
// deps change (pass the data that renders the cards, so it applies once they exist).
export function useLiquidGlassAll(selector: string, opts: GlassOpts, deps: DependencyList) {
  useEffect(() => {
    const handles = Array.from(document.querySelectorAll<HTMLElement>(selector)).map((el) => applyLiquidGlass(el, opts))
    return () => handles.forEach((h) => h.destroy())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
}

// Attach the ref to any element to give it liquid-glass refraction (frosted fallback off
// Chromium). The element should be translucent so there is a backdrop to bend.
export function useLiquidGlass<T extends HTMLElement>(opts?: GlassOpts) {
  const ref = useRef<T>(null)
  useEffect(() => {
    if (!ref.current) return
    const h = applyLiquidGlass(ref.current, opts)
    return () => h.destroy()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return ref
}
