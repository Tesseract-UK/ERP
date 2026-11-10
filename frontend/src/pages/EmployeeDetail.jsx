// Admin/HR: single employee's full picture — calendar, every request, and
// reporting-line management. Assigning a manager is the step that completes a
// new joiner's onboarding. Only an Admin can approve/reject here (override);
// the employee's own manager decides from Approvals.
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import MonthCalendar, { MonthNav } from '../components/MonthCalendar'
import {
  EmptyState, Field, Modal, NumberInput, Spinner, StatusBadge, fmtDate, fmtDateTime, fmtTime, titleCase, useToast,
} from '../components/ui'
import { CalendarDays, Users } from '../components/icons'
import { KindBadge } from '../components/RequestForms'
import { ConversationModal, DecisionFlow } from '../components/Conversation'

const ALLOCATION_TYPES = ['casual', 'sick', 'earned', 'maternity', 'paternity', 'optional_holiday', 'wfh']

function AttendanceCorrectionCard({ employee, onSaved }) {
  const toast = useToast()
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  const maxDate = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`
  const [date, setDate] = useState('')
  const [status, setStatus] = useState('absent')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    try {
      const result = await api.put(`/hr/employees/${employee.id}/attendance/${date}/correction`, { status, reason })
      toast(`Attendance marked ${titleCase(status)} for ${fmtDate(date)}`, 'success')
      setReason('')
      onSaved(result)
    } catch (error) {
      toast(error.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card">
      <div className="card-head"><h3>Correct Attendance</h3></div>
      <form className="card-body" onSubmit={submit}>
        <div className="form-row">
          <Field label="Completed date" required>
            <input className="input" type="date" required max={maxDate} value={date} onChange={(event) => setDate(event.target.value)} />
          </Field>
          <Field label="Correct status" required>
            <select className="input" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="absent">Absent</option><option value="present">Present</option>
            </select>
          </Field>
        </div>
        <Field label="Reason" required help="Required for the audit trail. Existing punch and location evidence is not changed.">
          <textarea className="input" required minLength={10} maxLength={1000} value={reason}
            onChange={(event) => setReason(event.target.value)} placeholder="Explain why this attendance status needs correction…" />
        </Field>
        <button className="btn" disabled={busy || !date}>{busy ? 'Saving…' : 'Save Attendance Correction'}</button>
      </form>
    </div>
  )
}

function AllocationsCard({ employeeId, readOnly }) {
  const toast = useToast()
  const [overrides, setOverrides] = useState(null)
  const [balance, setBalance] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.get(`/hr/employees/${employeeId}/leave-overrides`).then(setOverrides).catch((e) => toast(e.message, 'error'))
    api.get(`/hr/employees/${employeeId}/balance`).then(setBalance).catch(() => {})
  }, [employeeId, toast])
  useEffect(load, [load])

  const setOverride = (lt, value) => {
    setOverrides((o) => ({ ...o, [lt]: { ...o[lt], override: value } }))
  }

  // Copy the company policy into any field HR hasn't filled yet.
  const fillDefaults = () => setOverrides((o) => Object.fromEntries(Object.entries(o).map(
    ([lt, v]) => [lt, { ...v, override: v.override ?? v.company_default }])))

  const save = async () => {
    setBusy(true)
    try {
      const allocations = Object.fromEntries(
        Object.entries(overrides).map(([lt, v]) => [lt, v.override]))
      await api.put(`/hr/employees/${employeeId}/leave-overrides`, { allocations })
      toast('Allocations updated', 'success')
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!overrides) return <Spinner />

  return (
    <div className="card">
      <div className="card-head"><h3>Leave &amp; WFH Allocations</h3>
        {!readOnly && <div className="toolbar">
          <button className="btn ghost sm" onClick={fillDefaults} disabled={busy}>Fill from company policy</button>
          <button className="btn secondary sm" onClick={save} disabled={busy}>
            {busy ? 'Saving…' : 'Save'}</button>
        </div>}
      </div>
      <div className="card-body">
        {ALLOCATION_TYPES.map((lt) => {
          const wfhBal = lt === 'wfh' && balance?.wfh
          return (
            <div key={lt} style={{ padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>{lt === 'wfh' ? 'Work From Home (annual cap)' : `${titleCase(lt)} Leave`}</span>
                <NumberInput style={{ width: 110 }} min={0} max={365} disabled={readOnly}
                             value={overrides[lt].override}
                             onChange={(n) => setOverride(lt, n)}
                             placeholder={`0 · policy ${overrides[lt].company_default}`} />
              </div>
              {wfhBal && (
                <div className="help-text" style={{ marginTop: 4 }}>
                  Live balance: accrued {wfhBal.allocated} ({wfhBal.monthly_rate}/month so far) −
                  used {wfhBal.used} = remaining{' '}
                  <strong style={{ color: wfhBal.remaining < 0 ? 'var(--danger)' : 'var(--ink)' }}>
                    {wfhBal.remaining}
                  </strong>
                </div>
              )}
            </div>
          )
        })}
        <p className="help-text" style={{ marginTop: 10 }}>
          {readOnly && <strong>This is your own allocation — an Admin or another HR sets it. </strong>}
          Every balance starts at 0 until HR enters it here. Blank means 0. Use “Fill from
          company policy” to copy the standard numbers, adjust, then Save. WFH accrues monthly and can go negative if overused.
        </p>
      </div>
    </div>
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
  const { user } = useAuth()
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
  const [selectedRequest, setSelectedRequest] = useState(null)
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

  if (!emp) return <Spinner />

  const canHaveReports = ['manager', 'admin'].includes(emp.role)
  const managers = (orgData?.managers || []).filter((m) => m.id !== emp.id)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div>
          <h2>{emp.full_name}</h2>
          <div className="sub">{emp.employee_code} · {titleCase(emp.role)} · {emp.department || 'No department'}
            {emp.onboarding_pending && <> · <span className="badge warn">Awaiting onboarding</span></>}</div>
        </div>
        <Link to="/employees" className="btn secondary sm">← Back to Employees</Link>
      </div>

      <div className="grid cols-2">
        <div className="card pad">
          <div style={{ fontWeight: 600, marginBottom: 12 }}>Reporting Manager</div>
          {emp.role === 'admin' ? (
            <p className="help-text">Admins don't report to anyone.</p>
          ) : <>
            {emp.onboarding_pending && <div className="notice" style={{ marginBottom: 12 }}>
              <strong>Onboarding pending.</strong> Complete their details below and assign a manager —
              that unlocks their leave, WFH and regularization requests and notifies them.
            </div>}
            <div className="form-row" style={{ alignItems: 'end', marginBottom: 0 }}>
              <Field label="Manager" required>
                <select className="input" value={managerPick} onChange={(e) => setManagerPick(e.target.value)}>
                  <option value="" disabled>Select a manager…</option>
                  {managers.map((m) => <option key={m.id} value={m.id}>{m.full_name}{m.role === 'admin' ? ' (Admin)' : ''}</option>)}
                </select>
              </Field>
              <div className="toolbar" style={{ marginBottom: 14 }}>
                <button className="btn secondary sm" disabled={!managerPick || String(managerPick) === String(emp.manager_id)}
                        onClick={() => changeManager(managerPick)}>
                  {emp.manager_id ? 'Change manager' : 'Assign & complete onboarding'}
                </button>
              </div>
            </div>
          </>}
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

                  </div>
                ))}
            </div>
          </div>
        )}
      </div>

      <AllocationsCard employeeId={Number(id)} readOnly={Number(id) === user.id} />

      {user.role === 'admin' && <AttendanceCorrectionCard employee={emp} onSaved={(record) => {
        setCalData((current) => current ? {
          ...current,
          days: current.days.map((day) => day.date === record.date
            ? { ...day, status: record.status, detail: record }
            : day),
        } : current)
      }} />}

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
                    <tr key={`${r.kind}-${r.id}`} className={`row-${r.kind}`}>
                      <td><KindBadge kind={r.kind} />{r.kind === 'leave' && <div className="help-text">{titleCase(r.leave_type)}</div>}</td>
                      <td>{start === end ? fmtDate(start) : <>{fmtDate(start)} → {fmtDate(end)}</>}</td>
                      <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.reason}>{r.reason}</td>
                      <td><StatusBadge status={r.status} />
                        {r.approver_comment && <div className="help-text" title={r.approver_comment}>“{r.approver_comment}”</div>}</td>
                      <td>{r.approver_name || '—'}</td>
                      <td><div className="toolbar" style={{ gap: 6 }}>
                          <button className="btn ghost sm" onClick={() => setSelectedRequest(r)}>{user.role === 'admin' ? 'Conversation' : 'View'}</button>
                          {r.status === 'pending' && user.role === 'admin' && <>
                          <button className="btn success sm" onClick={() => setDecision({ item: r, decision: 'approve' })}>Approve</button>
                          <button className="btn danger sm" onClick={() => setDecision({ item: r, decision: 'reject' })}>Reject</button>
                          </>}
                        </div></td>
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
        <DecisionFlow request={{ ...decision.item, user: emp }} decision={decision.decision}
                      onClose={() => setDecision(null)}
                      onDone={() => { setDecision(null); loadRequests() }} />
      )}
      {selectedRequest && user.role === 'admin' && (
        <ConversationModal kind={selectedRequest.kind} id={selectedRequest.id}
                           onClose={() => setSelectedRequest(null)} onChanged={loadRequests} />
      )}
      {selectedRequest && user.role !== 'admin' && <Modal title="Request details" onClose={() => setSelectedRequest(null)}>
        <p><strong>Employee:</strong> {emp.full_name} ({emp.employee_code})</p>
        <p><strong>Type:</strong> <KindBadge kind={selectedRequest.kind} /> {selectedRequest.kind === 'leave' && titleCase(selectedRequest.leave_type)}</p>
        <p><strong>Date:</strong> {selectedRequest.start_date
          ? `${fmtDate(selectedRequest.start_date)} → ${fmtDate(selectedRequest.end_date)}`
          : fmtDate(selectedRequest.date)}</p>
        {selectedRequest.days != null && <p><strong>Working days:</strong> {selectedRequest.days}</p>}
        {selectedRequest.requested_check_in && <p><strong>Corrected check-in:</strong> {fmtTime(selectedRequest.requested_check_in)}</p>}
        {selectedRequest.requested_check_out && <p><strong>Corrected check-out:</strong> {fmtTime(selectedRequest.requested_check_out)}</p>}
        <p><strong>Reason:</strong> {selectedRequest.reason}</p>
        <p><strong>Status:</strong> {titleCase(selectedRequest.status)}{selectedRequest.approver_name ? ` · decided by ${selectedRequest.approver_name}` : ''}</p>
        <p><strong>Submitted:</strong> {fmtDateTime(selectedRequest.created_at)}{selectedRequest.decided_at ? ` · Decided ${fmtDateTime(selectedRequest.decided_at)}` : ''}</p>
        {selectedRequest.approver_comment && <p><strong>Decision note:</strong> {selectedRequest.approver_comment}</p>}
      </Modal>}
    </div>
  )
}
