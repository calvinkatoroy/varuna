import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth'
import Login from './pages/Login'
import ClientCockpit from './screens/ClientCockpit'

// v2 shell: each screen owns its own chrome (the studied-DNA hero band), so there is no shared
// sidebar Layout. Team/pipeline routes land in later frontend tasks. (v1 pages remain on disk,
// unrouted, until fully replaced.)
export default function App() {
  const { user, ready } = useAuth()
  if (!ready) return <div className="p-sm text-ink-faint">Loading…</div>
  if (!user) return <Login />

  return (
    <Routes>
      <Route path="/" element={<ClientCockpit />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
