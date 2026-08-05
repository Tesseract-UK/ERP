import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './AuthContext'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Onboarding from './pages/Onboarding'
import Dashboard from './pages/Dashboard'
import Attendance from './pages/Attendance'
import Leaves from './pages/Leaves'
import WFH from './pages/WFH'
import Regularization from './pages/Regularization'
import Profile from './pages/Profile'
import Approvals from './pages/Approvals'
import Team from './pages/Team'
import TeamCalendar from './pages/TeamCalendar'
import Employees from './pages/Employees'
import Policies from './pages/Policies'
import Reports from './pages/Reports'
import Announcements from './pages/Announcements'
import Organization from './pages/Organization'
import AuditLogs from './pages/AuditLogs'

// Route guard: requires login, and optionally one of the given roles (admin always passes).
function Guard({ roles, children }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (roles && user.role !== 'admin' && !roles.includes(user.role)) return <Navigate to="/" replace />
  return children
}

export default function App() {
  const { user, loading } = useAuth()
  if (loading) return <Spinner />

  // New joiners must complete their profile before anything else unlocks.
  if (user && user.profile_completed === false) {
    return <Onboarding />
  }

  return (
    <Routes>
      {/* Wildcard paths let Clerk manage its own sub-routes (OAuth callback, MFA, etc.). */}
      <Route path="/login/*" element={user ? <Navigate to="/" replace /> : <Login />} />
      <Route path="/signup/*" element={user ? <Navigate to="/" replace /> : <Signup />} />
      <Route element={<Guard><Layout /></Guard>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/attendance" element={<Attendance />} />
        <Route path="/leaves" element={<Leaves />} />
        <Route path="/wfh" element={<WFH />} />
        <Route path="/regularization" element={<Regularization />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/approvals" element={<Guard roles={['manager', 'hr']}><Approvals /></Guard>} />
        <Route path="/team" element={<Guard roles={['manager', 'hr']}><Team /></Guard>} />
        <Route path="/team-calendar" element={<Guard roles={['manager', 'hr']}><TeamCalendar /></Guard>} />
        <Route path="/employees" element={<Guard roles={['hr']}><Employees /></Guard>} />
        <Route path="/policies" element={<Guard roles={['hr']}><Policies /></Guard>} />
        <Route path="/reports" element={<Guard roles={['hr']}><Reports /></Guard>} />
        <Route path="/announcements" element={<Guard roles={['hr']}><Announcements /></Guard>} />
        <Route path="/organization" element={<Guard roles={[]}><Organization /></Guard>} />
        <Route path="/audit-logs" element={<Guard roles={[]}><AuditLogs /></Guard>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
