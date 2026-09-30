import { useEffect, useState } from 'react'

// Minimal toast: call toast('message') from anywhere; <Toaster/> (mounted once in App) shows a
// transient pill bottom-center. No dependency, no context.
type Listener = (msg: string) => void
let listeners: Listener[] = []

export function toast(msg: string) {
  listeners.forEach((l) => l(msg))
}

export function Toaster() {
  const [msg, setMsg] = useState<string | null>(null)
  useEffect(() => {
    let timer: any
    const l: Listener = (m) => {
      setMsg(m)
      clearTimeout(timer)
      timer = setTimeout(() => setMsg(null), 2600)
    }
    listeners.push(l)
    return () => { listeners = listeners.filter((x) => x !== l); clearTimeout(timer) }
  }, [])
  if (!msg) return null
  return (
    <div className="pointer-events-none fixed bottom-20 left-1/2 z-[80] -translate-x-1/2">
      <div className="rounded-pill border border-rule bg-card px-4 py-2.5 text-[13px] font-medium text-ink shadow-[0_16px_50px_rgba(0,0,0,.4)]">{msg}</div>
    </div>
  )
}
