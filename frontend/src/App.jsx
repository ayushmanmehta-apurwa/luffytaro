import { Suspense, lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Department from './pages/Department'
import Landing from './pages/Landing'
import Report from './pages/Report'
import TicketDetail from './pages/TicketDetail'
import { useApp } from './services/AppContext'

const Admin = lazy(() => import('./pages/Admin'))

function Guard({ roles, children }) {
  const { role } = useApp()
  if (!roles.includes(role)) {
    return (
      <div className="card p-8 max-w-xl">
        <h1 className="font-display text-2xl font-semibold">This screen is for a different role</h1>
        <p className="mt-2 text-navy-800/80">Use the role switcher in the sidebar to view as {roles.join(' or ')}. The switcher is a demo convenience, not real authentication.</p>
      </div>
    )
  }
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route element={<Layout />}>
        <Route path="/report" element={<Report />} />
        <Route path="/department" element={<Guard roles={['department', 'admin']}><Department /></Guard>} />
        <Route path="/admin" element={<Guard roles={['admin']}><Suspense fallback={<p className="text-sm">Loading dashboard...</p>}><Admin /></Suspense></Guard>} />
        <Route path="/tickets/:id" element={<TicketDetail />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
