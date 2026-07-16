import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import InstallAgent from './pages/InstallAgent'
import NewScan from './pages/NewScan'
import ActiveScans from './pages/ActiveScans'
import ApprovalQueue from './pages/ApprovalQueue'
import Reports from './pages/Reports'
import FindingsReview from './pages/FindingsReview'
import ManualInput from './pages/ManualInput'

export default function App() {
  const { user, ready } = useAuth()
  if (!ready) return <div className="p-8 text-gray-400">Loading…</div>
  if (!user) return <Login />
  const isPro = user.role === 'pro'

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/new" replace />} />
        <Route path="/install" element={<InstallAgent />} />
        <Route path="/new" element={<NewScan />} />
        <Route path="/scans" element={<ActiveScans />} />
        <Route path="/reports" element={<Reports />} />
        {isPro && <Route path="/approvals" element={<ApprovalQueue />} />}
        {isPro && <Route path="/findings" element={<FindingsReview />} />}
        {isPro && <Route path="/manual" element={<ManualInput />} />}
        <Route path="*" element={<Navigate to="/new" replace />} />
      </Routes>
    </Layout>
  )
}
