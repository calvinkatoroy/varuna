import { createContext, useCallback, useContext, useEffect, useRef, useState, ReactNode } from 'react'
import { api, setToken, getToken, refresh, UNAUTHORIZED_EVENT, PASSWORD_CHANGE_EVENT } from './api'
import type { Role } from './lib/roles'

type Me = { username: string; role: Role; org_id?: string | null; must_change_password?: boolean; name?: string }
type User = Me | null

interface AuthCtx {
  user: User
  ready: boolean
  login: (username: string, password: string, team?: boolean, code?: string) => Promise<Me>
  logout: () => void
  // Re-read /api/me (after the forced password change clears must_change_password).
  reloadMe: () => Promise<void>
}

const Ctx = createContext<AuthCtx>(null as any)

// The server ends idle sessions; a token refreshed every 20 minutes while the app is open keeps
// an active person signed in (a JWT lasts an hour).
const REFRESH_MS = 20 * 60 * 1000

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User>(null)
  const [ready, setReady] = useState(false)
  const lastRefresh = useRef(Date.now())

  // Restore session from a stored JWT on load. With no token, the app lands on the gate
  // (login over a blurred dashboard), see App + AuthGate.
  useEffect(() => {
    if (!getToken()) {
      setReady(true)
      return
    }
    // Team tokens are refused on the public plane (403); fall back to the private plane's /me.
    api
      .get('/api/me')
      .catch((e) => (e?.status === 403 ? api.pget('/api/me') : Promise.reject(e)))
      .then((me) => { setUser(me); lastRefresh.current = Date.now() })
      .catch(() => setToken(null))
      .finally(() => setReady(true))
  }, [])

  // Team accounts (and the system administrator) authenticate on the private plane (NFR-24); clients on the public one.
  async function login(username: string, password: string, team = false, code?: string) {
    const { token } = await (team ? api.ppost : api.post)('/api/login', { username, password, ...(code ? { code } : {}) })
    setToken(token)
    const me: Me = await (team ? api.pget : api.get)('/api/me')
    lastRefresh.current = Date.now()
    setUser(me)
    return me
  }

  function logout() {
    setToken(null)
    setUser(null)
  }

  const role = user?.role
  const reloadMe = useCallback(async () => {
    const me = await (role === 'client' ? api.get : api.pget)('/api/me')
    setUser(me)
  }, [role])

  // A 401 anywhere (api.ts) means the session is gone - without this, `user` stays populated
  // and every route gate (ClientRoute/RoleRoute) keeps rendering the app as if still logged in,
  // while every subsequent request just 401s again forever. Dropping `user` here is what
  // actually sends the page back to the login gate.
  // A 403 password_change_required flags the user so App shows the forced change dialog.
  useEffect(() => {
    const onUnauthorized = () => setUser(null)
    const onMustChange = () => setUser((u) => (u && !u.must_change_password ? { ...u, must_change_password: true } : u))
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    window.addEventListener(PASSWORD_CHANGE_EVENT, onMustChange)
    return () => {
      window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
      window.removeEventListener(PASSWORD_CHANGE_EVENT, onMustChange)
    }
  }, [])

  // Background refresh while signed in: every 20 minutes, plus once when the tab comes back after
  // being hidden longer than that (timers are throttled in background tabs). Only a 401 matters
  // (api.ts ends the session); anything else is ignored and retried on the next tick.
  const signedIn = !!user
  useEffect(() => {
    if (!signedIn) return
    const tick = () => {
      if (!getToken()) return
      lastRefresh.current = Date.now()
      refresh(role).catch(() => {})
    }
    const timer = setInterval(tick, REFRESH_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible' && Date.now() - lastRefresh.current > REFRESH_MS) tick()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [signedIn, role])

  return <Ctx.Provider value={{ user, ready, login, logout, reloadMe }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
