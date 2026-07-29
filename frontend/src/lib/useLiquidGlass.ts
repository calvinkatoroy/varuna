import { useEffect, useRef } from 'react'
import { applyLiquidGlass, type GlassOpts } from './liquidGlass'

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
