import { useEffect, useState } from 'react'
import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from './auth'
import { isMock } from './mock'
import ClientCockpit from './screens/ClientCockpit'
import ClientTasks from './screens/ClientTasks'
import ClientFindings from './screens/ClientFindings'
import ClientReports from './screens/ClientReports'
import { AuthGate } from './screens/AuthGate'
import { TeamLogin } from './screens/TeamLogin'
import ResetPassword from './screens/ResetPassword'
import { TwoFactor } from './components/TwoFactor'
import { ChangePassword } from './components/ChangePassword'
import { ClientShell } from './components/ClientShell'
import { api } from './api'
import TeamBoard from './screens/TeamBoard'
import FindingsReview from './screens/FindingsReview'
import SysAdmin from './screens/SysAdmin'
import Profile, { ConfirmEmail, SignedInRoute, RETURN_KEY } from './screens/Profile'
import { Splash } from './components/Splash'
import { Toaster } from './lib/toast'
import { useScrollRestore } from './lib/useScrollRestore'

const ACTIVATED = 'varuna-activated'

// The client area is gated as a whole: until the account is activated (login -> task ->
// pentester accepts -> agent -> unlock) AND the logged-in account is actually a client, every client
// route shows the blurred cockpit + AuthGate. The role check matters on top of the localStorage
// flag: without it, a team account that happens to share a browser with a previously-activated
// client session would see the client dashboard rendered as themselves.
// Activation persists (localStorage) so the unlock survives navigation and reloads.
// It is a layout route: once activated it renders ONE ClientShell and the tab pages fill its outlet.
function ClientGate() {
  const { user } = useAuth()
  // Activation is remembered per account, so a second user on this browser goes through onboarding.
  const [activated, setActivated] = useState(() => localStorage.getItem(ACTIVATED))
  if (user && user.role !== 'client') return <Navigate to="/team" replace />
  if (user?.role === 'client' && activated === user.username) return <ClientShell />
  return (
    <>
      <div aria-hidden className="pointer-events-none select-none saturate-[.85]" style={{ filter: 'blur(7px)' }}>
        <ClientShell><ClientCockpit /></ClientShell>
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
  const navigate = useNavigate()
  useScrollRestore()

  // Back to the page that asked for a sign-in (SignInFirst), e.g. an email confirmation link.
  useEffect(() => {
    if (!user) return
    let to: string | null = null
    try { to = sessionStorage.getItem(RETURN_KEY); sessionStorage.removeItem(RETURN_KEY) } catch {}
    if (to && to.startsWith('/')) navigate(to, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.username])

  return (
    <>
      <Splash />
      {ready && (
        <Routes>
          <Route path="/reset" element={<ResetPassword />} />
          <Route element={<ClientGate />}>
            <Route path="/" element={<ClientCockpit />} />
            <Route path="/tasks" element={<ClientTasks />} />
            <Route path="/findings" element={<ClientFindings />} />
            <Route path="/reports" element={<ClientReports />} />
          </Route>
          <Route path="/proposals" element={<Navigate to="/tasks" replace />} />
          <Route path="/team" element={<RoleRoute><TeamBoard /></RoleRoute>} />
          <Route path="/team/findings" element={<RoleRoute><FindingsReview /></RoleRoute>} />
          <Route path="/team/sysadmin" element={<RoleRoute sysadmin><SysAdmin /></RoleRoute>} />
          <Route path="/profile" element={<SignedInRoute why="Your profile is part of your account."><Profile /></SignedInRoute>} />
          <Route path="/confirm-email" element={<SignedInRoute why="Confirming a new email address needs you signed in as yourself."><ConfirmEmail /></SignedInRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      )}
      {/* Temporary password (new account or administrator reset): nothing else works until it is changed. */}
      {ready && user?.must_change_password && <ChangePassword forced onClose={() => { reloadMe().catch(() => {}) }} />}
      <Toaster />
    </>
  )
}
