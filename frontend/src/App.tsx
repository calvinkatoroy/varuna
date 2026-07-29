import { useState } from 'react'
import { useAuth } from './auth'
import ClientCockpit from './screens/ClientCockpit'
import { AuthGate } from './screens/AuthGate'

// Progressive-unlock entry: the dashboard is always the backdrop, blurred and locked behind the
// AuthGate until the account is activated (register → proposal → lead approval → agent → unlock).
// This is the visual form of the backend rule: an account is inert until a proposal is approved.
export default function App() {
  const { ready } = useAuth()
  const [active, setActive] = useState(false)
  if (!ready) return <div className="p-sm text-ink-faint">Loading…</div>
  const gated = !active

  return (
    <>
      <div
        aria-hidden={gated}
        className={gated ? 'pointer-events-none select-none saturate-[.85]' : ''}
        style={{ filter: gated ? 'blur(7px)' : 'blur(0px)', transition: 'filter .6s cubic-bezier(0.16,1,0.3,1)' }}
      >
        <ClientCockpit />
      </div>
      {gated && <AuthGate onActivate={() => setActive(true)} />}
    </>
  )
}
