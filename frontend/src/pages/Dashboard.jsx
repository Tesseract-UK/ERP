// Role-aware dashboard fed by a single /dashboard API call.
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import {
  EmptyState, Spinner, StatusBadge, fmtDate, fmtHours, fmtTime, titleCase, useToast,
} from '../components/ui'
import { AlertTriangle, ArrowRight, Cake, CalendarDays, Megaphone } from '../components/icons'
import OnboardingNotice from '../components/OnboardingNotice'

function Stat({ label, value, sub, danger }) {
  return (
    <div className="card stat">
      <div className="label">{label}</div>
      <div className="value" style={danger ? { color: 'var(--danger)' } : undefined}>{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}

function getLiveWorkHours(att, nowMs) {
  if (!att?.check_in || att?.check_out) return att?.work_hours ?? 0

  const checkInMs = Date.parse(att.check_in)
  if (Number.isNaN(checkInMs)) return att?.work_hours ?? 0

  const endMs = Math.max(nowMs, checkInMs)
  let workedMs = endMs - checkInMs

  for (const br of att.breaks || []) {
    const startMs = Date.parse(br.start)
    if (Number.isNaN(startMs)) continue

    const breakEndMs = br.end ? Date.parse(br.end) : endMs
    if (Number.isNaN(breakEndMs)) continue

    workedMs -= Math.max(0, Math.min(breakEndMs, endMs) - startMs)
  }

  return Math.max(workedMs / 3600000, 0)
}

function getCurrentLocation(requiredAccuracyMeters) {
  if (!navigator.geolocation) {
    return Promise.reject(new Error('This browser cannot provide location. Use a browser with location support.'))
  }

  return new Promise((resolve, reject) => {
    const watchTimeoutMs = 15000
    let bestPosition = null
    let watchId = null
    let settled = false

    const cleanup = () => {
      if (watchId !== null) navigator.geolocation.clearWatch(watchId)
      window.clearTimeout(timerId)
    }
    const finish = (callback, value) => {
      if (settled) return
      settled = true
      cleanup()
      callback(value)
    }
    const timerId = window.setTimeout(() => {
      if (bestPosition) {
        finish(reject, new Error(
          `Your best location fix is accurate to about ${Math.round(bestPosition.coords.accuracy)} m; ` +
          `attendance needs ${Math.round(requiredAccuracyMeters)} m or better. ` +
          'Move near a window or try again outdoors.'
        ))
      } else {
        finish(reject, new Error('The browser did not get a location fix within 15 seconds. Check device location services and this site’s location permission, then try again.'))
      }
    }, watchTimeoutMs)

    try {
      // Keep listening for a better GPS/Wi-Fi fix instead of submitting the
      // first coarse position. The backend independently enforces the same limit.
      watchId = navigator.geolocation.watchPosition(
        (position) => {
          if (!Number.isFinite(position.coords.accuracy) || position.coords.accuracy <= 0) return
          if (!bestPosition || position.coords.accuracy < bestPosition.coords.accuracy) {
            bestPosition = position
          }
          if (position.coords.accuracy <= requiredAccuracyMeters) finish(resolve, position)
        },
        (error) => {
          if (error.code === error.PERMISSION_DENIED) {
            finish(reject, new Error(
              `Your browser has blocked location access for ${window.location.origin}. ` +
              'Open this site’s permissions from the icon beside the address bar, set Location to Allow, reload the page, and try again. ' +
              'Attendance is not recorded without location access.'
            ))
          } else if (error.code === error.POSITION_UNAVAILABLE && !bestPosition) {
            finish(reject, new Error('Your location is unavailable. Check your device location settings and try again.'))
          }
        },
        { enableHighAccuracy: true, timeout: watchTimeoutMs, maximumAge: 30000 },
      )
    } catch {
      finish(reject, new Error('Your browser could not start location access. Check device location services and try again.'))
    }
  })
}

function CheckInPanel({ att, onRefresh, workedHours, maxGpsAccuracyMeters, recheckInSeconds = 0 }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const [recheckSeconds, setRecheckSeconds] = useState(recheckInSeconds)

  useEffect(() => setRecheckSeconds(recheckInSeconds), [recheckInSeconds, att?.check_out])
  useEffect(() => {
    if (recheckSeconds <= 0) return undefined
    const timer = window.setInterval(() => {
      setRecheckSeconds((remaining) => Math.max(remaining - 1, 0))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [recheckSeconds > 0])

  const act = async (path) => {
    setBusy(true)
    setActionError('')
    try {
      const payload = {}
      if (path === '/attendance/check-in' || path === '/attendance/check-out' || path === '/attendance/recheck-in') {
        const position = await getCurrentLocation(maxGpsAccuracyMeters)
        payload.latitude = position.coords.latitude
        payload.longitude = position.coords.longitude
        payload.accuracy_meters = position.coords.accuracy
      }
      await api.post(path, payload)
      setActionError('')
      toast(path.includes('check-in') ? 'Checked in. Have a great day!' :
            path.includes('check-out') ? 'Checked out. See you tomorrow!' : 'Done', 'success')
      onRefresh()
    } catch (err) {
      setActionError(err.message)
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
          {' '}· Worked: <strong>{fmtHours(workedHours)}</strong>
          {' '}· Breaks: <strong>{Math.round(att?.break_minutes || 0)}m</strong>
          {att?.overtime_hours > 0 && <> · Overtime: <strong>{fmtHours(att.overtime_hours)}</strong></>}
        </div>
      </div>
      <div className="toolbar">
        {!att?.check_in && <button className="btn success" disabled={busy} onClick={() => act('/attendance/check-in')}>Check In</button>}
        {att?.check_in && att?.check_out && recheckSeconds > 0 && (
          <button className="btn success" disabled={busy}
                  onClick={() => act('/attendance/recheck-in')}>
            {busy ? 'Rechecking…' : `Recheck In · 0:${String(recheckSeconds).padStart(2, '0')}`}
          </button>
        )}
        {att?.check_in && !att?.check_out && (
          <>
            {onBreak
              ? <button className="btn secondary" disabled={busy} onClick={() => act('/attendance/break/end')}>End Break</button>
              : <button className="btn secondary" disabled={busy} onClick={() => act('/attendance/break/start')}>Start Break</button>}
            <button className="btn danger" disabled={busy} onClick={() => act('/attendance/check-out')}>Check Out</button>
          </>
        )}
      </div>
      {actionError && <div role="alert" className="error-text" style={{ flexBasis: '100%', fontSize: 13, marginTop: 2 }}>{actionError}</div>}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [nowMs, setNowMs] = useState(Date.now())

  const load = useCallback(() => {
    api.get('/dashboard').then(setData).catch((e) => setError(e.message))
  }, [])
  useEffect(load, [load])

  useEffect(() => {
    const hasActiveAttendance = data?.today_attendance?.check_in && !data?.today_attendance?.check_out
    if (!hasActiveAttendance) return undefined

    const timer = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [data?.today_attendance?.check_in, data?.today_attendance?.check_out])

  if (error) return <EmptyState icon={AlertTriangle} title="Could not load dashboard" hint={error} />
  if (!data) return <Spinner />

  const att = data.today_attendance
  const workedHours = getLiveWorkHours(att, nowMs)
  const bal = data.balances
  const leaveRemaining = ['casual', 'sick', 'earned'].reduce((s, k) => s + (bal[k]?.remaining || 0), 0)
  const org = data.organization || data.team
  const isAdmin = user.role === 'admin'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h2>Hello, {user.full_name.split(' ')[0]}</h2>
          <div className="sub">{new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}</div>
        </div>
        {att && <StatusBadge status={att.status} />}
      </div>

      <OnboardingNotice />

      {!isAdmin && <CheckInPanel
        att={att}
        onRefresh={load}
        workedHours={workedHours}
        maxGpsAccuracyMeters={data.location_policy?.max_gps_accuracy_meters ?? 500}
        recheckInSeconds={data.recheck_in_seconds ?? 0}
      />}

      {isAdmin && <div className="grid cols-4">
        <Stat label="Awaiting Decision" value={data.pending_requests.awaiting_my_review}
              sub="Leave, WFH & regularization (Admin override)" />
        <Stat label="Awaiting Onboarding" value={data.pending_onboarding?.length ?? 0}
              sub="New joiners without a manager" />
        <Stat label="Upcoming Holidays" value={data.upcoming_holidays.length} sub="Next 30 days" />
        <Stat label="Company WFH Days" value={data.upcoming_company_wfh?.length ?? 0} sub="Next 30 days" />
      </div>}

      {!isAdmin && <div className="grid cols-4">
        <Stat label="Leave Balance" value={leaveRemaining}
              sub={`Casual ${bal.casual.remaining} · Sick ${bal.sick.remaining} · Earned ${bal.earned.remaining}`} />
        <Stat label="WFH Balance" value={bal.wfh.remaining} danger={bal.wfh.remaining < 0}
              sub={`of ${bal.wfh.allocated} accrued · ${bal.wfh.monthly_rate}/month`} />
        <Stat label="My Pending Requests" value={data.pending_requests.total}
              sub={`Leave ${data.pending_requests.leave} · WFH ${data.pending_requests.wfh} · Reg. ${data.pending_requests.regularization} · Other ${data.pending_requests.employee_request || 0}`} />
        <Stat label="Hours Today" value={fmtHours(workedHours)}
              sub={att?.overtime_hours > 0 ? `+${fmtHours(att.overtime_hours)} overtime` : 'Standard day: 8h'} />
      </div>}

      {data.pending_onboarding?.length > 0 && (
        <div className="card">
          <div className="card-head"><h3>New Joiners Awaiting Onboarding</h3></div>
          <div className="table-wrap"><table className="table">
            <thead><tr><th>Name</th><th>Email</th><th></th></tr></thead>
            <tbody>
              {data.pending_onboarding.map((e) => (
                <tr key={e.id}><td>{e.full_name}</td><td>{e.email}</td>
                  <td><Link className="btn secondary sm" to={`/employees/${e.id}`}>Complete onboarding</Link></td></tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}

      {org && (
        <div className="card">
          <div className="card-head"><h3>{data.organization ? 'Organization Today' : 'My Team Today'}</h3>
            {['manager', 'admin'].includes(user.role) && <Link className="btn secondary sm" to="/approvals">
              Review approvals <ArrowRight size={14} /></Link>}
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
          <div className="card-head"><h3>Upcoming Holidays &amp; WFH Days</h3></div>
          <div className="card-body">
            {data.upcoming_holidays.length === 0 && !data.upcoming_company_wfh?.length && <EmptyState icon={CalendarDays} title="No holidays in the next 30 days" />}
            {(data.upcoming_company_wfh || []).map((d) => (
              <div key={`wfh-${d.id}`} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span>{d.note} <span className="badge wfh">Company WFH</span></span>
                <strong>{fmtDate(d.date)}</strong>
              </div>
            ))}
            {data.upcoming_holidays.map((h) => (
              <div key={h.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                <span>{h.name} <span className="badge neutral">{titleCase(h.holiday_type)}</span></span>
                <strong>{fmtDate(h.date)}</strong>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-head"><h3>Birthdays</h3></div>
          <div className="card-body">
            {data.birthdays.length === 0 && <EmptyState icon={Cake} title="No birthdays coming up" />}
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
            {data.announcements.length === 0 && <EmptyState icon={Megaphone} title="No announcements yet" />}
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
