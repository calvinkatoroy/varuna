import { useEffect, useRef, useState } from 'react'
import anime from 'animejs'
import { Shield } from 'lucide-react'

// A short branded buffer so fonts + charts finish loading before the app shows, hides the
// inconsistent asset pop-in, then fades out.
export function Splash() {
  const [gone, setGone] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const start = Date.now()
    let done = false
    const finish = () => {
      if (done) return
      done = true
      const wait = Math.max(0, 600 - (Date.now() - start))
      setTimeout(() => {
        if (!ref.current || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return setGone(true)
        anime({ targets: ref.current, opacity: [1, 0], duration: 420, easing: 'easeOutQuad', complete: () => setGone(true) })
      }, wait)
    }
    const fonts = (document as any).fonts
    fonts?.ready ? fonts.ready.then(finish) : finish()
    // Hard cap: never let a hung font/asset load keep the black splash up.
    const cap = setTimeout(finish, 1600)
    return () => clearTimeout(cap)
  }, [])

  if (gone) return null
  return (
    <div ref={ref} className="fixed inset-0 z-[100] grid place-items-center bg-shell">
      <div className="flex flex-col items-center gap-4">
        <span
          className="grid h-14 w-14 animate-pulse place-items-center rounded-2xl"
          style={{ background: 'conic-gradient(from 210deg,#F26A43,#f4996d,#F26A43)', boxShadow: 'inset 0 0 0 2px rgba(255,255,255,.16)' }}
        >
          <Shield size={28} className="fill-white text-white" />
        </span>
        <div className="text-[13px] font-medium text-ink-muted">Loading Varuna…</div>
      </div>
    </div>
  )
}
