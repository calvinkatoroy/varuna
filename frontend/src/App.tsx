import { useState } from 'react'
import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import ClientCockpit from './screens/ClientCockpit'
import { AuthGate } from './screens/AuthGate'
import TeamBoard from './screens/TeamBoard'
import { Splash } from './components/Splash'

// Client view: dashboard is the blurred backdrop, locked behind the AuthGate until the account
// is activated (register → proposal → lead approval → agent → unlock).
function GatedClient() {
  const [active, setActive] = useState(false)
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

const pill = (on: boolean) =>
  `rounded-pill px-4 py-1.5 text-[12.5px] font-semibold transition-colors ${on ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`

// Prototype-only: real app routes by role (client → cockpit, team → board). This lets you
// explore both worlds while everything runs on mock data.
function PrototypeSwitcher() {
  const loc = useLocation()
  return (
    <div className="fixed bottom-4 left-1/2 z-[60] flex -translate-x-1/2 items-center gap-1 rounded-pill border border-rule bg-card/90 p-1 shadow-[0_12px_40px_rgba(0,0,0,.3)] backdrop-blur">
      <span className="px-2 text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">Preview</span>
      <Link to="/" className={pill(loc.pathname === '/')}>Client</Link>
      <Link to="/team" className={pill(loc.pathname === '/team')}>Team</Link>
    </div>
  )
}

export default function App() {
  const { ready } = useAuth()
  return (
    <>
      <Splash />
      {ready && (
        <>
          <Routes>
            <Route path="/" element={<GatedClient />} />
            <Route path="/team" element={<TeamBoard />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <PrototypeSwitcher />
        </>
      )}
    </>
  )
}
