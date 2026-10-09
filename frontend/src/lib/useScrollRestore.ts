import { useEffect, useLayoutEffect, useRef } from 'react'
import { useLocation, useNavigationType } from 'react-router-dom'
import { restoring, scrollTarget } from './scroll'

// BrowserRouter has no <ScrollRestoration/>, so this does it: the scroll position is remembered per history
// entry (location.key); back/forward restores it, a new path starts at the top. A query-only change (the
// findings accordion rewrites ?target= with replace) never touches the scroll.
const saved = new Map<string, number>()
let token = 0   // bumped by every path change (restore) and on unmount: a running restore loop stops when it no longer matches

function restore(y: number, remembered: boolean) {
  const mine = ++token
  restoring.on = remembered
  let tries = 0
  const done = () => { if (mine === token) restoring.on = false }
  const step = () => {
    if (mine !== token) return
    const room = document.documentElement.scrollHeight - window.innerHeight
    // The page may still be growing (cached rows render at once, the rest follows): wait up to ~30 frames.
    if (y <= room || tries >= 30) {
      window.scrollTo({ top: y, left: 0, behavior: 'instant' as ScrollBehavior })
      done()
      requestAnimationFrame(() => requestAnimationFrame(() => delete document.documentElement.dataset.navigating))
      return
    }
    tries++
    requestAnimationFrame(step)
  }
  step()
}

export function useScrollRestore() {
  const { pathname, key } = useLocation()
  const type = useNavigationType()
  const keyRef = useRef(key)
  const pathRef = useRef(pathname)

  useEffect(() => {
    try { history.scrollRestoration = 'manual' } catch { /* old browsers */ }
    const onScroll = () => {
      saved.set(keyRef.current, window.scrollY)
      if (saved.size > 60) saved.delete(saved.keys().next().value as string)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => { window.removeEventListener('scroll', onScroll); token++; restoring.on = false; delete document.documentElement.dataset.navigating }
  }, [])

  useLayoutEffect(() => {
    keyRef.current = key
    if (pathRef.current === pathname) return
    pathRef.current = pathname
    document.documentElement.dataset.navigating = '1'   // index.css: no hero transition while the scroll resets
    const y = saved.get(key)
    restore(scrollTarget(type, y), type === 'POP' && y !== undefined)
  }, [key, pathname, type])
}
