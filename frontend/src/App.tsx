import { useState } from 'react'
import { Routes, Route, Navigate, Link, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import ClientCockpit from './screens/ClientCockpit'
import ClientProposals from './screens/ClientProposals'
import ClientFindings from './screens/ClientFindings'
import ClientReports from './screens/ClientReports'
import { AuthGate } from './screens/AuthGate'
import TeamBoard from './screens/TeamBoard'
import FindingsReview from './screens/FindingsReview'
import { Splash } from './components/Splash'

const ACTIVATED = 'varuna-activated'

// The client area is gated as a whole: until the account is activated (register → proposal →
// lead approval → agent → unlock), every client route shows the blurred cockpit + AuthGate.
// Activation persists (localStorage) so the unlock survives navigation and reloads.
function ClientRoute({ children }: { children: React.ReactNode }) {
  const [active, setActive] = useState(() => localStorage.getItem(ACTIVATED) === '1')
  if (active) return <>{children}</>
  return (
    <>
      <div
        aria-hidden
        className="pointer-events-none select-none saturate-[.85]"
        style={{ filter: 'blur(7px)' }}
      >
        <ClientCockpit />
      </div>
      <AuthGate onActivate={() => { localStorage.setItem(ACTIVATED, '1'); setActive(true) }} />
    </>
  )
}

const pill = (on: boolean) =>
  `rounded-pill px-4 py-1.5 text-[12.5px] font-semibold transition-colors ${on ? 'bg-accent text-white' : 'text-ink-muted hover:text-ink'}`

// Prototype-only: real app routes by role (client vs team). This lets you explore both worlds
// on mock data. "Reset" clears the unlock so you can re-demo the onboarding gate.
function PrototypeSwitcher() {
  const loc = useLocation()
  const team = loc.pathname.startsWith('/team')
  const reset = () => { localStorage.removeItem(ACTIVATED); location.assign('/') }
  return (
    <div className="fixed bottom-4 left-1/2 z-[60] flex -translate-x-1/2 items-center gap-1 rounded-pill border border-rule bg-card/90 p-1 shadow-[0_12px_40px_rgba(0,0,0,.3)] backdrop-blur">
      <span className="px-2 text-[10.5px] font-semibold uppercase tracking-wide text-ink-faint">Preview</span>
      <Link to="/" viewTransition className={pill(!team)}>Client</Link>
      <Link to="/team" viewTransition className={pill(team)}>Team</Link>
      <button onClick={reset} className="rounded-pill px-3 py-1.5 text-[12.5px] font-medium text-ink-faint hover:text-ink">Reset</button>
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
            <Route path="/" element={<ClientRoute><ClientCockpit /></ClientRoute>} />
            <Route path="/proposals" element={<ClientRoute><ClientProposals /></ClientRoute>} />
            <Route path="/findings" element={<ClientRoute><ClientFindings /></ClientRoute>} />
            <Route path="/reports" element={<ClientRoute><ClientReports /></ClientRoute>} />
            <Route path="/team" element={<TeamBoard />} />
            <Route path="/team/findings" element={<FindingsReview />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <PrototypeSwitcher />
        </>
      )}
    </>
  )
}
