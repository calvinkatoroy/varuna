import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { api, setToken, getToken } from './api'
import { isMock } from './mock'

type User = { username: string; role: string } | null

interface AuthCtx {
  user: User
  ready: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const Ctx = createContext<AuthCtx>(null as any)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User>(null)
  const [ready, setReady] = useState(false)

  // Restore session from a stored JWT on load. In mock mode, auto-authenticate as the sample
  // client so the prototype lands straight in the app (no login friction).
  useEffect(() => {
    if (isMock()) {
      setToken('mock.jwt.client')
      api.get('/api/me').then(setUser).finally(() => setReady(true))
      return
    }
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

  async function login(username: string, password: string) {
    const { token } = await api.post('/api/login', { username, password })
    setToken(token)
    setUser(await api.get('/api/me'))
  }

  function logout() {
    setToken(null)
    setUser(null)
  }

  return <Ctx.Provider value={{ user, ready, login, logout }}>{children}</Ctx.Provider>
}

export const useAuth = () => useContext(Ctx)
