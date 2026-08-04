// App shell: sidebar navigation, topbar with notifications, role-aware menu.
import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import { fmtDateTime, initials } from './ui'
import {
  LayoutDashboard, Clock, Plane, Home, PenLine, User, CheckSquare, Users,
  CalendarDays, IdCard, ClipboardList, BarChart3, Megaphone, Building2,
  ShieldCheck, Bell, Menu, Logo,
} from './icons'

const NAV = [
  { section: 'My Workspace', items: [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/attendance', label: 'Attendance', icon: Clock },
    { to: '/leaves', label: 'Leaves', icon: Plane },
    { to: '/wfh', label: 'Work From Home', icon: Home },
    { to: '/regularization', label: 'Regularization', icon: PenLine },
    { to: '/profile', label: 'My Profile', icon: User },
  ]},
  { section: 'Team', roles: ['manager', 'hr', 'admin'], items: [
    { to: '/approvals', label: 'Approvals', icon: CheckSquare },
    { to: '/team', label: 'Team Attendance', icon: Users },
    { to: '/team-calendar', label: 'Team Calendar', icon: CalendarDays },
  ]},
  { section: 'HR', roles: ['hr', 'admin'], items: [
    { to: '/employees', label: 'Employees', icon: IdCard },
    { to: '/policies', label: 'Policies & Holidays', icon: ClipboardList },
    { to: '/reports', label: 'Reports', icon: BarChart3 },
    { to: '/announcements', label: 'Announcements', icon: Megaphone },
  ]},
  { section: 'Administration', roles: ['admin'], items: [
    { to: '/organization', label: 'Organization', icon: Building2 },
    { to: '/audit-logs', label: 'Audit Logs', icon: ShieldCheck },
  ]},
]

const TITLES = {
  '/': 'Dashboard', '/attendance': 'Attendance', '/leaves': 'Leave Management',
  '/wfh': 'Work From Home', '/regularization': 'Attendance Regularization',
  '/profile': 'My Profile', '/approvals': 'Approvals', '/team': 'Team Attendance',
  '/team-calendar': 'Team Calendar', '/employees': 'Employee Management',
  '/policies': 'Policies & Holidays', '/reports': 'Reports',
  '/announcements': 'Announcements', '/organization': 'Organization Settings',
  '/audit-logs': 'Audit Logs',
}

function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState({ unread: 0, items: [] })
  const ref = useRef(null)

  const load = () => api.get('/notifications').then(setData).catch(() => {})
  useEffect(() => {
    load()
    const id = setInterval(load, 60000) // light polling; push can come later
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const close = (e) => ref.current && !ref.current.contains(e.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const markAll = async () => { await api.post('/notifications/read-all'); load() }

  return (
    <div className="bell-wrap" ref={ref}>
      <button className="bell" onClick={() => setOpen(!open)} aria-label="Notifications">
        <Bell size={16} />{data.unread > 0 && <span className="dot">{data.unread}</span>}
      </button>
      {open && (
        <div className="notif-panel">
          <div className="notif-item" style={{ display: 'flex', justifyContent: 'space-between' }}>
            <strong>Notifications</strong>
            {data.unread > 0 && <button className="btn ghost sm" onClick={markAll}>Mark all read</button>}
          </div>
          {data.items.length === 0 && <div className="notif-item">You're all caught up</div>}
          {data.items.map((n) => (
            <div key={n.id} className={`notif-item${n.is_read ? '' : ' unread'}`}
                 onClick={() => !n.is_read && api.post(`/notifications/${n.id}/read`).then(load)}>
              <div className="t">{n.title}</div>
              {n.body && <div className="b">{n.body}</div>}
              <div className="time">{fmtDateTime(n.created_at)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => setMenuOpen(false), [location.pathname])

  return (
    <div className="shell">
      {menuOpen && <div className="sidebar-backdrop" onClick={() => setMenuOpen(false)} />}
      <aside className={`sidebar${menuOpen ? ' open' : ''}`}>
        <div className="logo"><span className="cube"><Logo size={19} /></span> Tesseract HRMS</div>
        <nav>
          {NAV.filter((s) => !s.roles || s.roles.includes(user.role)).map((s) => (
            <div key={s.section}>
              <div className="nav-section">{s.section}</div>
              {s.items.map((i) => (
                <NavLink key={i.to} to={i.to} end={i.to === '/'}>
                  <span className="icon"><i.icon size={16} strokeWidth={1.8} /></span>{i.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <div className="main">
        <header className="topbar">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button className="menu-btn" onClick={() => setMenuOpen(true)} aria-label="Menu">
              <Menu size={17} /></button>
            <div className="page-title">{TITLES[location.pathname] || 'Tesseract HRMS'}</div>
          </div>
          <div className="right">
            <NotificationBell />
            <div className="userchip">
              <div className="meta">
                <div className="name">{user.full_name}</div>
                <div className="role">{user.role}</div>
              </div>
              <div className="avatar">{initials(user.full_name)}</div>
            </div>
            <button className="btn ghost sm" onClick={logout}>Sign out</button>
          </div>
        </header>
        <main className="content"><Outlet /></main>
      </div>
    </div>
  )
}
