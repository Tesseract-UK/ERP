
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './AuthContext'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import Login from './pages/Login'
import AdminLogin from './pages/AdminLogin'
import Signup from './pages/Signup'
import Dashboard from './pages/Dashboard'
import Attendance from './pages/Attendance'
import Leaves from './pages/Leaves'
import Conversations from './pages/Conversations'
import Regularization from './pages/Regularization'
import Profile from './pages/Profile'
import Approvals from './pages/Approvals'
import Requests from './pages/Requests'
import Team from './pages/Team'
import TeamCalendar from './pages/TeamCalendar'
import Employees from './pages/Employees'
import EmployeeDetail from './pages/EmployeeDetail'
import Policies from './pages/Policies'
import Reports from './pages/Reports'
import Announcements from './pages/Announcements'
import Organization from './pages/Organization'
import AuditLogs from './pages/AuditLogs'

// Login required; admin always passes role checks unless `noAdmin` is set
// (Admins have no attendance and never raise leave/WFH/regularization).
function Guard({ roles, noAdmin, children }) {
  const { user } = useAuth()

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (noAdmin && user.role === 'admin') {
    return <Navigate to="/" replace />
  }

  if (
    roles &&
    user.role !== 'admin' &&
    !roles.includes(user.role)
  ) {
    return <Navigate to="/" replace />
  }

  return children
}

export default function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return <Spinner />
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={user ? <Navigate to="/" replace /> : <Login />}
      />

      <Route
        path="/admin"
        element={user ? <Navigate to="/" replace /> : <AdminLogin />}
      />

      <Route
        path="/signup"
        element={user ? <Navigate to="/" replace /> : <Signup />}
      />

      <Route element={<Guard><Layout /></Guard>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/attendance" element={<Guard noAdmin><Attendance /></Guard>} />
        <Route path="/leaves" element={<Guard noAdmin><Leaves /></Guard>} />
        <Route path="/wfh" element={<Navigate to="/leaves" replace />} />
        <Route path="/regularization" element={<Guard noAdmin><Regularization /></Guard>} />
        <Route path="/conversations" element={<Conversations />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/requests" element={<Requests />} />

        <Route
          path="/approvals"
          element={
            <Guard roles={['manager']}>
              <Approvals />
            </Guard>
          }
        />

        <Route
          path="/team"
          element={
            <Guard roles={['manager', 'hr']}>
              <Team />
            </Guard>
          }
        />

        <Route
          path="/team-calendar"
          element={
            <Guard roles={['manager', 'hr']}>
              <TeamCalendar />
            </Guard>
          }
        />

        <Route
          path="/employees"
          element={
            <Guard roles={['hr']}>
              <Employees />
            </Guard>
          }
        />

        <Route
          path="/employees/:id"
          element={
            <Guard roles={['hr']}>
              <EmployeeDetail />
            </Guard>
          }
        />

        <Route
          path="/policies"
          element={
            <Guard roles={['hr']}>
              <Policies />
            </Guard>
          }
        />

        <Route
          path="/reports"
          element={
            <Guard roles={['hr']}>
              <Reports />
            </Guard>
          }
        />

        <Route
          path="/announcements"
          element={
            <Guard roles={['hr']}>
              <Announcements />
            </Guard>
          }
        />

        <Route
          path="/organization"
          element={
            <Guard roles={[]}>
              <Organization />
            </Guard>
          }
        />

        <Route
          path="/audit-logs"
          element={
            <Guard roles={[]}>
              <AuditLogs />
            </Guard>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
