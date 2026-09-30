import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { api, setToken, getToken, UNAUTHORIZED_EVENT } from './api'

type User = { username: string; role: string } | null

interface AuthCtx {
  user: User
  ready: boolean
  login: (username: string, password: string, team?: boolean) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => void
}

const Ctx = createContext<AuthCtx>(null as any)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User>(null)
  const [ready, setReady] = useState(false)

  // Restore session from a stored JWT on load. With no token, the app lands on the gate
  // (login/register over a blurred dashboard), see App + AuthGate.
  useEffect(() => {
    if (!getToken()) {
      setReady(true)
      return
    }
    api
      .get('/api/me')
      .then((me) => setUser(me))
      .catch(() => setToken(null))
      .finally(() => setReady(true))
  }, [])

  // Team accounts authenticate on the private plane (NFR-24); clients on the public one.
  async function login(username: string, password: string, team = false) {
    const { token } = await (team ? api.ppost : api.post)('/api/login', { username, password })
    setToken(token)
    setUser(await api.get('/api/me'))
  }

  async function register(username: string, password: string) {
    const { token } = await api.post('/api/register', { username, password })
    setToken(token)
    setUser(await api.get('/api/me'))
  }

  function logout() {
    setToken(null)
    setUser(null)
  }

  // A 401 anywhere (api.ts) means the session is gone - without this, `user` stays populated
  // and every route gate (ClientRoute/RoleRoute) keeps rendering the app as if still logged in,
  // while every subsequent request just 401s again forever. Dropping `user` here is what
  // actually sends the page back to the login gate.
  useEffect(() => {
    const onUnauthorized = () => setUser(null)
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  return <Ctx.Provider value={{ user, ready, login, register, logout }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
