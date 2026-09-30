import { useEffect, useState } from 'react'
import { flushSync } from 'react-dom'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './auth'
import { isMock } from './mock'
import ClientCockpit from './screens/ClientCockpit'
import ClientProposals from './screens/ClientProposals'
import ClientFindings from './screens/ClientFindings'
import ClientReports from './screens/ClientReports'
import { AuthGate } from './screens/AuthGate'
import { TeamLogin } from './screens/TeamLogin'
import { TwoFactor } from './components/TwoFactor'
import { api } from './api'
import TeamBoard from './screens/TeamBoard'
import FindingsReview from './screens/FindingsReview'
import TeamAccounts from './screens/TeamAccounts'
import { Splash } from './components/Splash'
import { Toaster } from './lib/toast'

const ACTIVATED = 'varuna-activated'

// The client area is gated as a whole: until the account is activated (register -> proposal ->
// lead approval -> agent -> unlock) AND the logged-in account is actually a client, every client
// route shows the blurred cockpit + AuthGate. The role check matters on top of the localStorage
// flag: without it, a team account that happens to share a browser with a previously-activated
// client session would see the client dashboard rendered as themselves.
// Activation persists (localStorage) so the unlock survives navigation and reloads.
function ClientRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  // Activation is remembered per account, so a second user on this browser goes through onboarding.
  const [activated, setActivated] = useState(() => localStorage.getItem(ACTIVATED))
  if (user && user.role !== 'client') return <Navigate to="/team" replace />
  if (user?.role === 'client' && activated === user.username) return <>{children}</>
  return (
    <>
      <div aria-hidden className="pointer-events-none select-none saturate-[.85]" style={{ filter: 'blur(7px)' }}>
        <ClientCockpit />
      </div>
      <AuthGate onActivate={(name) => { localStorage.setItem(ACTIVATED, name); setActivated(name) }} />
    </>
  )
}

// The private/team plane: gated on role, not just presence of a session, so a client account
// can't reach it just by navigating to /team. Dev note: seeded team logins in the mock are
// riyan/dimas/aisah/hani (any password) - see mock/index.ts's teamAccounts.
//
// Demo build (VITE_MOCK=1) skips the login gate entirely - there's no real backend session to
// protect, so it silently logs in as `admin` (mock lead_pentester) instead of making a visitor
// type credentials into a prototype. Real deployments (VITE_MOCK=0) still require a real login.
function RoleRoute({ children }: { children: React.ReactNode }) {
  const { user, login } = useAuth()
  useEffect(() => {
    if (isMock() && (!user || user.role === 'client')) login('admin', '').catch(() => {})
  }, [user, login])
  // Policy (VARUNA_REQUIRE_MFA): a team member without two-factor sees only the enrolment dialog.
  const [mustEnrol, setMustEnrol] = useState<boolean | null>(null)
  const team = !isMock() && !!user && user.role !== 'client'
  useEffect(() => {
    if (team) api.pget('/api/mfa').then((r) => setMustEnrol(r.required && !r.enabled)).catch(() => setMustEnrol(false))
  }, [team, user?.username])
  if (isMock()) return <>{children}</>
  if (team && mustEnrol === null) return null
  if (team) return mustEnrol ? <TwoFactor forced onClose={() => setMustEnrol(false)} /> : <>{children}</>
  return <TeamLogin />
}

export default function App() {
  const { ready } = useAuth()
  const location = useLocation()
  const [displayed, setDisplayed] = useState(location)

  // Page transition: drive the View Transitions API manually so it fires on every route change
  // (react-router's viewTransition prop silently no-ops with <BrowserRouter>). Old + new pages
  // are captured and cross-animated via the ::view-transition-* rules in index.css.
  useEffect(() => {
    if (location.pathname === displayed.pathname) return
    // Snap scroll to top BEFORE the old-page snapshot is taken. Otherwise the old snapshot is
    // captured at the current scroll position while the new page always renders at scroll 0,
    // so any named element (e.g. the nav pill) jumps between two different viewport positions.
    window.scrollTo(0, 0)
    const doc = document as any
    if (!doc.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setDisplayed(location)
      return
    }
    doc.startViewTransition(() => flushSync(() => setDisplayed(location)))
  }, [location, displayed])

  return (
    <>
      <Splash />
      {ready && (
        <Routes location={displayed}>
          <Route path="/" element={<ClientRoute><ClientCockpit /></ClientRoute>} />
          <Route path="/proposals" element={<ClientRoute><ClientProposals /></ClientRoute>} />
          <Route path="/findings" element={<ClientRoute><ClientFindings /></ClientRoute>} />
          <Route path="/reports" element={<ClientRoute><ClientReports /></ClientRoute>} />
          <Route path="/team" element={<RoleRoute><TeamBoard /></RoleRoute>} />
          <Route path="/team/findings" element={<RoleRoute><FindingsReview /></RoleRoute>} />
          <Route path="/team/accounts" element={<RoleRoute><TeamAccounts /></RoleRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      )}
      <Toaster />
    </>
  )
}
