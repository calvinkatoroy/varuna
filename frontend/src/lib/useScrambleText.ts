import { useEffect, useRef, useState } from 'react'

const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

// Scrambles into `target` over `duration`ms once `active` flips true: reveals characters
// left-to-right while the rest cycle through random glyphs (skipping spaces/punctuation so
// those don't flicker). Meant for a value that arrives from the API after a static loading
// placeholder - triggering on `active` going false->true turns that swap into a quick decode
// instead of a sudden pop, matched to the real value's own letter count.
export function useScrambleText(target: string, active: boolean, duration = 600) {
  const [text, setText] = useState(target)
  const frame = useRef<number>()

  useEffect(() => {
    if (!active) { setText(target); return }
    const start = performance.now()
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration)
      const revealCount = Math.floor(progress * target.length)
      setText(
        target
          .split('')
          .map((ch, i) => (i < revealCount || !/[a-zA-Z0-9]/.test(ch) ? ch : CHARS[Math.floor(Math.random() * CHARS.length)]))
          .join(''),
      )
      if (progress < 1) frame.current = requestAnimationFrame(tick)
    }
    frame.current = requestAnimationFrame(tick)
    return () => { if (frame.current) cancelAnimationFrame(frame.current) }
  }, [target, active, duration])

  return text
}
