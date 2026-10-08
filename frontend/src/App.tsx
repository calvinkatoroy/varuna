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
import ResetPassword from './screens/ResetPassword'
import { TwoFactor } from './components/TwoFactor'
import { ChangePassword } from './components/ChangePassword'
import { api } from './api'
import TeamBoard from './screens/TeamBoard'
import FindingsReview from './screens/FindingsReview'
import SysAdmin from './screens/SysAdmin'
import { Splash } from './components/Splash'
import { Toaster } from './lib/toast'

const ACTIVATED = 'varuna-activated'

// The client area is gated as a whole: until the account is activated (login -> proposal ->
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
// riyan/dimas/aisah/hani/bayu/sysadmin (any password) - see mock/index.ts's teamAccounts.
//
// The system administrator has no access to tenant data, so its whole app is the console
// (`sysadmin` routes); it is sent there from every other team route, and staff are kept out of it.
//
// Demo build (VITE_MOCK=1) skips the login gate entirely - there's no real backend session to
// protect, so it silently logs in as `admin` (mock lead_pentester), or `sysadmin` on the console,
// instead of making a visitor type credentials into a prototype. Real deployments (VITE_MOCK=0)
// still require a real login.
function RoleRoute({ children, sysadmin }: { children: React.ReactNode; sysadmin?: boolean }) {
  const { user, login } = useAuth()
  useEffect(() => {
    if (!isMock()) return
    if (sysadmin ? user?.role !== 'sysadmin' : !user || user.role === 'client' || user.role === 'sysadmin') {
      login(sysadmin ? 'sysadmin' : 'admin', '').catch(() => {})
    }
  }, [user, login, sysadmin])
  // Policy (VARUNA_REQUIRE_MFA): a team member without two-factor sees only the enrolment dialog.
  const [mustEnrol, setMustEnrol] = useState<boolean | null>(null)
  const team = !isMock() && !!user && user.role !== 'client'
  // A temporary password comes first (App shows the forced change dialog); the two-factor check follows it.
  const mustChange = !!user?.must_change_password
  useEffect(() => {
    if (team && !mustChange) api.pget('/api/mfa').then((r) => setMustEnrol(r.required && !r.enabled)).catch(() => setMustEnrol(false))
  }, [team, mustChange, user?.username])
  if (isMock()) return <>{children}</>
  if (team && (mustChange || mustEnrol === null)) return null
  if (team && mustEnrol) return <TwoFactor forced onClose={() => setMustEnrol(false)} />
  if (team && !!sysadmin !== (user.role === 'sysadmin')) return <Navigate to={sysadmin ? '/team' : '/team/sysadmin'} replace />
  if (team) return <>{children}</>
  return <TeamLogin />
}

export default function App() {
  const { ready, user, reloadMe } = useAuth()
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
          <Route path="/reset" element={<ResetPassword />} />
          <Route path="/" element={<ClientRoute><ClientCockpit /></ClientRoute>} />
          <Route path="/proposals" element={<ClientRoute><ClientProposals /></ClientRoute>} />
          <Route path="/findings" element={<ClientRoute><ClientFindings /></ClientRoute>} />
          <Route path="/reports" element={<ClientRoute><ClientReports /></ClientRoute>} />
          <Route path="/team" element={<RoleRoute><TeamBoard /></RoleRoute>} />
          <Route path="/team/findings" element={<RoleRoute><FindingsReview /></RoleRoute>} />
          <Route path="/team/sysadmin" element={<RoleRoute sysadmin><SysAdmin /></RoleRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      )}
      {/* Temporary password (new account or administrator reset): nothing else works until it is changed. */}
      {ready && user?.must_change_password && <ChangePassword forced onClose={() => { reloadMe().catch(() => {}) }} />}
      <Toaster />
    </>
  )
}
