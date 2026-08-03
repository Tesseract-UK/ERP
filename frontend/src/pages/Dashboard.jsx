// Role-aware dashboard fed by a single /dashboard API call.
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, localNowIso } from '../api'
import { useAuth } from '../AuthContext'
import {
  EmptyState, Spinner, StatusBadge, fmtDate, fmtHours, fmtTime, titleCase, useToast,
} from '../components/ui'

function Stat({ label, value, sub }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}

function CheckInPanel({ att, onRefresh }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)

  const act = async (path) => {
    setBusy(true)
    try {
      const payload = { local_time: localNowIso() }
      if (path === '/attendance/check-in') {
        // Capture geolocation when the browser allows it; never block check-in on it.
        try {
          const pos = await new Promise((res, rej) =>
            navigator.geolocation.getCurrentPosition(res, rej, { timeout: 4000 }))
          payload.latitude = pos.coords.latitude
          payload.longitude = pos.coords.longitude
        } catch { /* location denied or unavailable */ }
      }
      await api.post(path, payload)
      toast(path.includes('check-in') ? 'Checked in. Have a great day!' :
            path.includes('check-out') ? 'Checked out. See you tomorrow!' : 'Done', 'success')
      onRefresh()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const onBreak = att?.on_break
  return (
    <div className="card pad" style={{ display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center', justifyContent: 'space-between' }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: 15 }}>
          {!att?.check_in ? "You haven't checked in yet"
            : att.check_out ? 'Your day is complete'
            : onBreak ? 'You are on a break'
            : 'You are checked in'}
        </div>
        <div style={{ color: 'var(--ink-2)', fontSize: 13, marginTop: 3 }}>
          In: <strong>{fmtTime(att?.check_in)}</strong> · Out: <strong>{fmtTime(att?.check_out)}</strong>
          {' '}· Worked: <strong>{fmtHours(att?.work_hours)}</strong>
          {' '}· Breaks: <strong>{Math.round(att?.break_minutes || 0)}m</strong>
          {att?.overtime_hours > 0 && <> · Overtime: <strong>{fmtHours(att.overtime_hours)}</strong></>}
        </div>
      </div>
      <div className="toolbar">
        {!att?.check_in && <button className="btn success" disabled={busy} onClick={() => act('/attendance/check-in')}>Check In</button>}
        {att?.check_in && !att?.check_out && (
          <>
            {onBreak
              ? <button className="btn secondary" disabled={busy} onClick={() => act('/attendance/break/end')}>End Break</button>
              : <button className="btn secondary" disabled={busy} onClick={() => act('/attendance/break/start')}>Start Break</button>}
            <button className="btn danger" disabled={busy} onClick={() => act('/attendance/check-out')}>Check Out</button>
          </>
        )}
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.get('/dashboard').then(setData).catch((e) => setError(e.message))
  }, [])
  useEffect(load, [load])

  if (error) return <EmptyState icon="⚠️" title="Could not load dashboard" hint={error} />
  if (!data) return <Spinner />

  const att = data.today_attendance
  const bal = data.balances
  const leaveRemaining = ['casual', 'sick', 'earned'].reduce((s, k) => s + (bal[k]?.remaining || 0), 0)
  const org = data.organization || data.team

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h2>Hello, {user.full_name.split(' ')[0]} 👋</h2>
          <div className="sub">{new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</div>
        </div>
        {att && <StatusBadge status={att.status} />}
      </div>

      <CheckInPanel att={att} onRefresh={load} />

      <div className="grid cols-4">
        <Stat label="Leave Balance" value={leaveRemaining}
              sub={`Casual ${bal.casual.remaining} · Sick ${bal.sick.remaining} · Earned ${bal.earned.remaining}`} />
        <Stat label="WFH Balance" value={bal.wfh.remaining} sub={`of ${bal.wfh.allocated} this year`} />
        <Stat label="My Pending Requests" value={data.pending_requests.total}
              sub={`Leave ${data.pending_requests.leave} · WFH ${data.pending_requests.wfh} · Reg. ${data.pending_requests.regularization}`} />
        <Stat label="Hours Today" value={fmtHours(att?.work_hours ?? 0)}
              sub={att?.overtime_hours > 0 ? `+${fmtHours(att.overtime_hours)} overtime` : 'Standard day: 8h'} />
      </div>

      {org && (
        <div className="card">
          <div className="card-head"><h3>{data.organization ? 'Organization Today' : 'My Team Today'}</h3>
            {user.role !== 'employee' && <Link className="btn secondary sm" to="/approvals">Review approvals →</Link>}
          </div>
          <div className="card-body grid cols-4" style={{ padding: 14 }}>
            <Stat label="Members" value={org.total_members} />
            <Stat label="Present" value={org.present_today} sub={`${org.late_today} late`} />
            <Stat label="On Leave" value={org.on_leave_today} />
            <Stat label="Working From Home" value={org.wfh_today} />
          </div>
        </div>
      )}

      <div className="grid cols-3">
        <div className="card">
          <div className="card-head"><h3>Upcoming Holidays</h3></div>
          <div className="card-body">
            {data.upcoming_holidays.length === 0 && <EmptyState icon="🗓" title="No holidays in the next 30 days" />}
            {data.upcoming_holidays.map((h) => (
              <div key={h.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span>{h.name} <span className="badge neutral">{titleCase(h.holiday_type)}</span></span>
                <strong>{fmtDate(h.date)}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-head"><h3>Birthdays 🎂</h3></div>
          <div className="card-body">
            {data.birthdays.length === 0 && <EmptyState icon="🎈" title="No birthdays coming up" />}
            {data.birthdays.map((b, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span>{b.name}</span><strong>{fmtDate(b.date)}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-head"><h3>Announcements</h3></div>
          <div className="card-body">
            {data.announcements.length === 0 && <EmptyState icon="📢" title="No announcements yet" />}
            {data.announcements.map((a) => (
              <div key={a.id} style={{ padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ fontWeight: 600 }}>{a.title}</div>
                <div style={{ color: 'var(--ink-2)', fontSize: 12.5 }}>{a.body}</div>
                <div style={{ color: 'var(--ink-3)', fontSize: 11.5, marginTop: 2 }}>{a.created_by} · {fmtDate(a.created_at)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {data.recent_employees && (
        <div className="card">
          <div className="card-head"><h3>Recently Added Employees</h3></div>
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Name</th><th>Code</th><th>Department</th><th>Role</th></tr></thead>
            <tbody>
              {data.recent_employees.map((e) => (
                <tr key={e.id}><td>{e.full_name}</td><td>{e.employee_code}</td>
                    <td>{e.department || '—'}</td><td>{titleCase(e.role)}</td></tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}
    </div>
  )
}
