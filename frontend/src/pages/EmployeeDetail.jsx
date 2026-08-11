// Admin/HR: single employee's full picture — calendar, every request with
// approve/reject authority, and reporting-line management (assign/remove
// their manager, and if they're a manager themselves, manage who reports
// to them).
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import MonthCalendar, { MonthNav } from '../components/MonthCalendar'
import {
  EmptyState, Field, Modal, Spinner, StatusBadge, fmtDate, titleCase, useToast,
} from '../components/ui'
import { CalendarDays, Users } from '../components/icons'

const KIND_LABEL = { leave: 'Leave', wfh: 'Work From Home', regularization: 'Regularization' }

function DecisionModal({ item, decision, onClose, onDone }) {
  const toast = useToast()
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      await api.post(`/approvals/${item.kind}/${item.id}/${decision}`, { comment: comment || null })
      toast(`Request ${decision === 'approve' ? 'approved' : 'rejected'}`, 'success')
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const label = item.kind === 'leave' ? `${titleCase(item.leave_type)} Leave` : KIND_LABEL[item.kind]

  return (
    <Modal title={`${decision === 'approve' ? 'Approve' : 'Reject'} ${label} request`}
           onClose={onClose} footer={
      <>
        <button className="btn secondary" onClick={onClose} disabled={busy}>Cancel</button>
        <button className={`btn ${decision === 'approve' ? 'success' : 'danger'}`}
                onClick={submit} disabled={busy}>
          {busy ? 'Working…' : decision === 'approve' ? 'Approve' : 'Reject'}
        </button>
      </>
    }>
      <p style={{ marginBottom: 12, color: 'var(--ink-2)' }}>Reason: “{item.reason}”</p>
      <Field label="Comment (optional)" help="Stored with the request for future reference">
        <textarea className="input" value={comment} onChange={(e) => setComment(e.target.value)}
                  placeholder="Add a note for the employee…" />
      </Field>
    </Modal>
  )
}

function AddReportModal({ managerId, onClose, onDone }) {
  const toast = useToast()
  const [candidates, setCandidates] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/hr/employees?unassigned=true&page_size=100')
      .then((d) => setCandidates(d.items.filter((c) => c.id !== managerId)))
      .catch((e) => toast(e.message, 'error'))
  }, [managerId, toast])

  const assign = async (empId) => {
    setBusy(true)
    try {
      await api.post(`/hr/employees/${empId}/set-manager`, { manager_id: managerId })
      toast('Added to team', 'success')
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Add Direct Report" onClose={onClose}>
      {candidates === null ? <Spinner /> : candidates.length === 0
        ? <EmptyState icon={Users} title="No unassigned employees"
                      hint="Everyone active already reports to a manager." />
        : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {candidates.map((c) => (
              <div key={c.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
                <div>
                  <strong>{c.full_name}</strong>
                  <div className="help-text">{c.employee_code} · {titleCase(c.role)}</div>
                </div>
                <button className="btn secondary sm" disabled={busy} onClick={() => assign(c.id)}>Add</button>
              </div>
            ))}
          </div>
        )}
    </Modal>
  )
}

export default function EmployeeDetail() {
  const { id } = useParams()
  const toast = useToast()
  const now = new Date()

  const [emp, setEmp] = useState(null)
  const [requests, setRequests] = useState(null)
  const [reports, setReports] = useState(null)
  const [orgData, setOrgData] = useState(null)
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 })
  const [calData, setCalData] = useState(null)
  const [managerPick, setManagerPick] = useState('')
  const [decision, setDecision] = useState(null)
  const [showAddReport, setShowAddReport] = useState(false)

  const loadEmp = useCallback(() => {
    api.get(`/hr/employees/${id}`).then((e) => { setEmp(e); setManagerPick(e.manager_id || '') })
       .catch((err) => toast(err.message, 'error'))
  }, [id, toast])
  useEffect(loadEmp, [loadEmp])

  const loadRequests = useCallback(() => {
    api.get(`/hr/employees/${id}/requests`).then(setRequests).catch((err) => toast(err.message, 'error'))
  }, [id, toast])
  useEffect(loadRequests, [loadRequests])

  const loadReports = useCallback(() => {
    api.get(`/hr/employees?manager_id=${id}&page_size=100&include_inactive=true`)
       .then((d) => setReports(d.items)).catch(() => {})
  }, [id])
  useEffect(loadReports, [loadReports])

  useEffect(() => { api.get('/admin/org-data').then(setOrgData).catch(() => {}) }, [])

  useEffect(() => {
    setCalData(null)
    api.get(`/team/calendar/${id}?year=${ym.year}&month=${ym.month}`)
       .then(setCalData).catch((err) => toast(err.message, 'error'))
  }, [id, ym, toast])

  const changeManager = async (managerId) => {
    try {
      await api.post(`/hr/employees/${id}/set-manager`, { manager_id: managerId ? Number(managerId) : null })
      toast('Manager updated', 'success')
      loadEmp()
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const removeReport = async (reportId, name) => {
    try {
      await api.post(`/hr/employees/${reportId}/set-manager`, { manager_id: null })
      toast(`${name} removed from this manager`, 'success')
      loadReports()
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  if (!emp) return <Spinner />

  const canHaveReports = ['manager', 'hr', 'admin'].includes(emp.role)
  const managers = (orgData?.managers || []).filter((m) => m.id !== emp.id)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h2>{emp.full_name}</h2>
          <div className="sub">{emp.employee_code} · {titleCase(emp.role)} · {emp.department || 'No department'}</div>
        </div>
        <Link to="/employees" className="btn secondary sm">← Back to Employees</Link>
      </div>

      <div className="grid cols-2">
        <div className="card pad">
          <div style={{ fontWeight: 600, marginBottom: 12 }}>Reporting Manager</div>
          <div className="form-row" style={{ alignItems: 'end', marginBottom: 0 }}>
            <Field label="Manager">
              <select className="input" value={managerPick} onChange={(e) => setManagerPick(e.target.value)}>
                <option value="">— None —</option>
                {managers.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
              </select>
            </Field>
            <div className="toolbar" style={{ marginBottom: 14 }}>
              <button className="btn secondary sm" onClick={() => changeManager(managerPick)}>
                {emp.manager_id ? 'Update' : 'Assign'}
              </button>
              {emp.manager_id && (
                <button className="btn ghost sm" style={{ color: 'var(--danger)' }}
                        onClick={() => changeManager(null)}>Remove</button>
              )}
            </div>
          </div>
        </div>

        {canHaveReports && (
          <div className="card">
            <div className="card-head"><h3>Direct Reports</h3>
              <button className="btn secondary sm" onClick={() => setShowAddReport(true)}>+ Add Report</button>
            </div>
            <div className="card-body">
              {reports === null ? <Spinner /> : reports.length === 0
                ? <EmptyState icon={Users} title="No direct reports yet" />
                : reports.map((r) => (
                  <div key={r.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
                    <div>
                      <Link to={`/employees/${r.id}`}>{r.full_name}</Link>
                      <div className="help-text">{r.employee_code}</div>
                    </div>
                    <button className="btn ghost sm" style={{ color: 'var(--danger)' }}
                            onClick={() => removeReport(r.id, r.full_name)}>Remove</button>
                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Attendance Calendar</h3>
          <MonthNav year={ym.year} month={ym.month} onChange={(year, month) => setYm({ year, month })} />
        </div>
        <div className="card-body">
          {calData ? <MonthCalendar data={calData} /> : <Spinner />}
        </div>
      </div>

      <div className="card">
        <div className="card-head"><h3>Requests</h3></div>
        {requests === null ? <Spinner /> : requests.length === 0
          ? <EmptyState icon={CalendarDays} title="No requests yet" />
          : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Type</th><th>Dates</th><th>Reason</th><th>Status</th><th>Reviewed By</th><th></th></tr></thead>
              <tbody>
                {requests.map((r) => {
                  const start = r.start_date || r.date
                  const end = r.end_date || r.date
                  return (
                    <tr key={`${r.kind}-${r.id}`}>
                      <td>{r.kind === 'leave' ? `${titleCase(r.leave_type)} Leave` : KIND_LABEL[r.kind]}</td>
                      <td>{start === end ? fmtDate(start) : <>{fmtDate(start)} → {fmtDate(end)}</>}</td>
                      <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.reason}>{r.reason}</td>
                      <td><StatusBadge status={r.status} />
                        {r.approver_comment && <div className="help-text" title={r.approver_comment}>“{r.approver_comment}”</div>}</td>
                      <td>{r.approver_name || '—'}</td>
                      <td>{r.status === 'pending' && (
                        <div className="toolbar" style={{ gap: 6 }}>
                          <button className="btn success sm" onClick={() => setDecision({ item: r, decision: 'approve' })}>Approve</button>
                          <button className="btn danger sm" onClick={() => setDecision({ item: r, decision: 'reject' })}>Reject</button>
                        </div>
                      )}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table></div>
          )}
      </div>

      {showAddReport && (
        <AddReportModal managerId={Number(id)} onClose={() => setShowAddReport(false)}
                        onDone={() => { setShowAddReport(false); loadReports() }} />
      )}
      {decision && (
        <DecisionModal item={decision.item} decision={decision.decision}
                       onClose={() => setDecision(null)}
                       onDone={() => { setDecision(null); loadRequests() }} />
      )}
    </div>
  )
}
