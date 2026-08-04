// My attendance: monthly color-coded calendar. Click any date to see its
// detail, or to quick-apply for Leave/WFH on that date. Below the calendar,
// track every Leave/WFH request raised for the month shown, with live status.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import MonthCalendar, { MonthNav } from '../components/MonthCalendar'
import { LeaveApplyForm, WfhApplyForm } from '../components/RequestForms'
import { EmptyState, Modal, Spinner, StatusBadge, fmtDate, titleCase, useToast } from '../components/ui'
import { CalendarDays } from '../components/icons'

export default function Attendance() {
  const now = new Date()
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 })
  const [data, setData] = useState(null)
  const [leaveRows, setLeaveRows] = useState(null)
  const [wfhRows, setWfhRows] = useState(null)
  const [applyType, setApplyType] = useState(null) // 'leave' | 'wfh' | null
  const toast = useToast()

  useEffect(() => {
    setData(null)
    api.get(`/attendance/calendar?year=${ym.year}&month=${ym.month}`)
      .then(setData)
      .catch((e) => toast(e.message, 'error'))
  }, [ym, toast])

  const loadRequests = useCallback(() => {
    api.get('/leaves').then(setLeaveRows).catch(() => {})
    api.get('/wfh').then(setWfhRows).catch(() => {})
  }, [])
  useEffect(loadRequests, [loadRequests])

  const requests = leaveRows && wfhRows ? [
    ...leaveRows,
    ...wfhRows.map((r) => ({ ...r, start_date: r.date, end_date: r.date })),
  ] : []

  const monthStart = `${ym.year}-${String(ym.month).padStart(2, '0')}-01`
  const monthEnd = `${ym.year}-${String(ym.month).padStart(2, '0')}-31`
  const monthRequests = requests
    .filter((r) => r.start_date <= monthEnd && r.end_date >= monthStart)
    .sort((a, b) => a.start_date.localeCompare(b.start_date))

  const monthLabel = new Date(ym.year, ym.month - 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card">
        <div className="card-head">
          <h3>Monthly Attendance</h3>
          <MonthNav year={ym.year} month={ym.month} onChange={(year, month) => setYm({ year, month })} />
        </div>
        <div className="card-body">
          {data
            ? <MonthCalendar data={data} selfService requests={requests}
                              onChanged={() => { loadRequests(); setYm({ ...ym }) }} />
            : <Spinner />}
          <p className="help-text" style={{ marginTop: 12 }}>
            Click any date to see login time, logout time, working hours, breaks and status —
            or to apply for Leave / Work From Home on that date.
            Forgot to check in or out? Submit a request from the Regularization page.
          </p>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Requests — {monthLabel}</h3>
          <div className="toolbar">
            <button className="btn secondary sm" onClick={() => setApplyType('leave')}>+ Apply for Leave</button>
            <button className="btn secondary sm" onClick={() => setApplyType('wfh')}>+ Request WFH</button>
          </div>
        </div>
        {leaveRows === null || wfhRows === null ? <Spinner /> : monthRequests.length === 0
          ? <EmptyState icon={CalendarDays} title="No requests this month"
                        hint="Leave and WFH requests you raise for this month will appear here." />
          : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Type</th><th>Dates</th><th>Reason</th><th>Status</th><th>Reviewed By</th></tr></thead>
              <tbody>
                {monthRequests.map((r) => (
                  <tr key={`${r.kind}-${r.id}`}>
                    <td>{r.kind === 'leave' ? `${titleCase(r.leave_type)} Leave` : 'Work From Home'}</td>
                    <td>{r.start_date === r.end_date ? fmtDate(r.start_date)
                                                      : <>{fmtDate(r.start_date)} → {fmtDate(r.end_date)}</>}</td>
                    <td style={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.reason}>{r.reason}</td>
                    <td><StatusBadge status={r.status} />
                      {r.approver_comment && <div className="help-text" title={r.approver_comment}>“{r.approver_comment}”</div>}</td>
                    <td>{r.approver_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
      </div>

      {applyType === 'leave' && (
        <Modal title="Apply for Leave" onClose={() => setApplyType(null)}>
          <LeaveApplyForm onCancel={() => setApplyType(null)}
                          onDone={() => { setApplyType(null); loadRequests() }} />
        </Modal>
      )}
      {applyType === 'wfh' && (
        <Modal title="Request Work From Home" onClose={() => setApplyType(null)}>
          <WfhApplyForm onCancel={() => setApplyType(null)}
                        onDone={() => { setApplyType(null); loadRequests() }} />
        </Modal>
      )}
    </div>
  )
}
