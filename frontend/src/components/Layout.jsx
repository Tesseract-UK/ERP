// App shell: sidebar navigation, topbar with notifications, role-aware menu.
import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api, API_BASE } from '../api'
import { useAuth } from '../AuthContext'
import { fmtDate, fmtDateTime, fmtTime, initials, Modal, titleCase, useToast } from './ui'
import {
  LayoutDashboard, Clock, Plane, Home, PenLine, User, CheckSquare, Users,
  CalendarDays, IdCard, ClipboardList, BarChart3, Megaphone, Building2,
  ShieldCheck, Bell, Menu, Logo, MessageSquare,
} from './icons'

const NAV = [
  { section: 'My Workspace', items: [
    { to: '/', label: 'Dashboard', icon: LayoutDashboard },
    { to: '/attendance', label: 'Attendance', icon: Clock },
    { to: '/leaves', label: 'Leaves', icon: Plane },
    { to: '/wfh', label: 'Work From Home', icon: Home },
    { to: '/regularization', label: 'Regularization', icon: PenLine },
    { to: '/requests', label: 'Requests', icon: MessageSquare },
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
  '/profile': 'My Profile', '/requests': 'Employee Requests', '/approvals': 'Approvals', '/team': 'Team Attendance',
  '/team-calendar': 'Team Calendar', '/employees': 'Employee Management',
  '/policies': 'Policies & Holidays', '/reports': 'Reports',
  '/announcements': 'Announcements', '/organization': 'Organization Settings',
  '/audit-logs': 'Audit Logs',
}

function NotificationCenter() {
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [data, setData] = useState({ unread: 0, items: [] })
  const [selected, setSelected] = useState(null)

  const load = () => api.get('/notifications').then(setData).catch(() => {})
  useEffect(() => {
    load()
    const id = setInterval(load, 60000) // light polling; push can come later
    return () => clearInterval(id)
  }, [])

  const markAll = async () => {
    try { await api.post('/notifications/read-all'); load() }
    catch (error) { toast(error.message, 'error') }
  }

  const openNotification = async (notification) => {
    try {
      const detail = await api.get(`/notifications/${notification.id}`)
      if (!notification.is_read) await api.post(`/notifications/${notification.id}/read`)
      setOpen(false)
      setSelected(detail)
      load()
    } catch (error) { toast(error.message, 'error') }
  }

  const request = selected?.request
  const documentPath = request?.document_path || request?.attachment_path
  const documentUrl = documentPath
    ? `${API_BASE}/files/${documentPath.split(/[\\/]/).map(encodeURIComponent).join('/')}`
    : null

  return (
    <>
      <button type="button" className="sidebar-notifications" onClick={() => setOpen(true)}>
        <span className="icon"><Bell size={16} strokeWidth={1.8} /></span>
        <span>Notifications</span>
        {data.unread > 0 && <span className="nav-count">{data.unread > 99 ? '99+' : data.unread}</span>}
      </button>
      {open && <Modal title="Notifications" wide onClose={() => setOpen(false)} footer={
        data.unread > 0 ? <button className="btn ghost sm" onClick={markAll}>Mark all read</button> : null
      }>
        <div className="notification-list">
          {data.items.length === 0 && <div className="notif-item">You're all caught up</div>}
          {data.items.map((n) => (
            <button type="button" key={n.id} className={`notif-item${n.is_read ? '' : ' unread'}`}
              onClick={() => openNotification(n)}>
              <div className="t">{n.title}</div>
              {n.body && <div className="b">{n.body}</div>}
              <div className="time">{n.actor_name ? `${n.kind === 'announcement' ? 'Announced by' : 'From'} ${n.actor_name} · ` : ''}{fmtDateTime(n.created_at)}</div>
            </button>
          ))}
        </div>
      </Modal>}
      {selected && <Modal title={selected.announcement?.title || selected.title} onClose={() => setSelected(null)}>
        <div className="help-text" style={{ marginBottom: 12 }}>
          {selected.announcement
            ? <>Announced by <strong>{selected.announcement.created_by || selected.actor_name || 'Unknown'}</strong> · {fmtDateTime(selected.announcement.created_at)}</>
            : <>{selected.actor_name ? `From ${selected.actor_name}` : 'System notification'} · {fmtDateTime(selected.created_at)}</>}
        </div>
        {(selected.announcement?.body || selected.body) && <p style={{ whiteSpace: 'pre-wrap', marginBottom: 14 }}>{selected.announcement?.body || selected.body}</p>}
        {request && <div className="card-body" style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 8 }}>
          {request.user && <p><strong>Employee:</strong> {request.user.full_name} ({request.user.employee_code})</p>}
          {request.requester_name && <p><strong>Requester:</strong> {request.requester_name} · {titleCase(request.category)} · {titleCase(request.priority)}</p>}
          {request.title && <p><strong>Request:</strong> {request.title}</p>}
          {request.kind === 'leave' && <p><strong>Leave:</strong> {titleCase(request.leave_type)} · {fmtDate(request.start_date)} to {fmtDate(request.end_date)} · {request.days} day(s)</p>}
          {request.kind === 'wfh' && <p><strong>WFH date:</strong> {fmtDate(request.date)}</p>}
          {request.kind === 'regularization' && <p><strong>Correction date:</strong> {fmtDate(request.date)} · In {fmtTime(request.requested_check_in)} · Out {fmtTime(request.requested_check_out)}</p>}
          <p><strong>{request.description ? 'Description' : 'Reason'}:</strong> {request.reason || request.description || '—'}</p>
          <p><strong>Status:</strong> {titleCase(request.status)}{request.approval_stage ? <> · <strong>Stage:</strong> {titleCase(request.approval_stage)}</> : null}</p>
          <p><strong>Submitted:</strong> {fmtDateTime(request.created_at)}{request.decided_at ? ` · Decided ${fmtDateTime(request.decided_at)}` : ''}</p>
          {request.manager_comment && <p><strong>Manager comment:</strong> {request.manager_comment}</p>}
          {request.hr_comment && <p><strong>HR comment:</strong> {request.hr_comment}</p>}
          {request.approver_comment && <p><strong>Decision comment:</strong> {request.approver_comment}</p>}
          {documentUrl && <p style={{ marginTop: 12 }}><a href={documentUrl} target="_blank" rel="noreferrer">Open supporting document</a></p>}
          {request.messages?.length > 0 && <div style={{ marginTop: 14 }}><strong>Conversation</strong>{request.messages.map((message) =>
            <p key={message.id} className="help-text" style={{ marginTop: 8 }}><strong>{message.user_name}</strong> · {fmtDateTime(message.created_at)}<br />{message.body}</p>)}</div>}
        </div>}
        {selected.details_unavailable && <p className="help-text">The linked request is no longer available.</p>}
      </Modal>}
    </>
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
        <div className="logo"><Logo size={22} /><span>Tesseract HRMS</span></div>
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
          <NotificationCenter />
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
