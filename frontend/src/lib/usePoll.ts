import { useEffect, useRef } from 'react'
import { nextDelay, pollExpired } from './audit'

/** Poll `run` while `key` is set. Stops when `done(result)` is true, when `key` changes or on unmount. A failed poll
 *  (quiet request) is simply tried again. The callbacks are read through a ref, so only `key` restarts the loop.
 *  `limit`: after `maxMs` the loop stops and `onTimeout` runs once. */
export function usePoll<T>(key: string | null, run: () => Promise<T>, done: (v: T) => boolean, onTick: (v: T) => void, limit?: { maxMs: number; onTimeout: () => void }) {
  const fns = useRef({ run, done, onTick, limit })
  fns.current = { run, done, onTick, limit }
  useEffect(() => {
    if (!key) return
    let live = true
    let timer: ReturnType<typeof setTimeout>
    let attempt = 0
    const t0 = Date.now()
    const step = async () => {
      try {
        const v = await fns.current.run()
        if (!live) return
        fns.current.onTick(v)
        if (fns.current.done(v)) return
      } catch {
        if (!live) return
      }
      const l = fns.current.limit
      if (l && pollExpired(t0, Date.now(), l.maxMs)) { l.onTimeout(); return }
      timer = setTimeout(step, nextDelay(attempt++))
    }
    timer = setTimeout(step, nextDelay(attempt++))
    return () => { live = false; clearTimeout(timer) }
  }, [key])
}
