import { useEffect, useRef } from 'react'
import { nextDelay } from './audit'

/** Poll `run` while `key` is set. Stops when `done(result)` is true, when `key` changes or on unmount. A failed poll
 *  (quiet request) is simply tried again. The callbacks are read through a ref, so only `key` restarts the loop. */
export function usePoll<T>(key: string | null, run: () => Promise<T>, done: (v: T) => boolean, onTick: (v: T) => void) {
  const fns = useRef({ run, done, onTick })
  fns.current = { run, done, onTick }
  useEffect(() => {
    if (!key) return
    let live = true
    let timer: ReturnType<typeof setTimeout>
    let attempt = 0
    const step = async () => {
      try {
        const v = await fns.current.run()
        if (!live) return
        fns.current.onTick(v)
        if (fns.current.done(v)) return
      } catch {
        if (!live) return
      }
      timer = setTimeout(step, nextDelay(attempt++))
    }
    timer = setTimeout(step, nextDelay(attempt++))
    return () => { live = false; clearTimeout(timer) }
  }, [key])
}
