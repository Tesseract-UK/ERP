// Team attendance with filters and pagination (manager/HR/admin).
import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  EmptyState, Field, Modal, Pagination, Spinner, StatusBadge, fmtDate, fmtDateTime, fmtHours,
  fmtTime, titleCase, useToast,
} from '../components/ui'
import { Users } from '../components/icons'
import { useAuth } from '../AuthContext'

function AttendanceCorrectionModal({ initial, onClose, onDone }) {
  const toast = useToast()
  const [employeeId, setEmployeeId] = useState(initial?.user?.id ? String(initial.user.id) : '')
  const [employeeName, setEmployeeName] = useState(initial?.user?.full_name || '')
  const [employeeSearch, setEmployeeSearch] = useState('')
  const [matches, setMatches] = useState([])
  const [date, setDate] = useState(initial?.date || '')
  const [status, setStatus] = useState(initial?.status === 'absent' ? 'present' : 'absent')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const yesterday = new Date()
  yesterday.setDate(yesterday.getDate() - 1)
  const maxDate = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, '0')}-${String(yesterday.getDate()).padStart(2, '0')}`

  useEffect(() => {
    if (employeeId || employeeSearch.trim().length < 2) {
      setMatches([])
      return undefined
    }
    let cancelled = false
    const timer = setTimeout(() => {
      const query = new URLSearchParams({ search: employeeSearch.trim(), include_inactive: 'true', page: 1, page_size: 25 })
      api.get(`/hr/employees?${query}`).then((result) => {
        if (!cancelled) setMatches(result.items || [])
      }).catch((err) => { if (!cancelled) toast(err.message, 'error') })
    }, 250)
    return () => { cancelled = true; clearTimeout(timer) }
  }, [employeeId, employeeSearch, toast])

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    try {
      await api.put(`/hr/employees/${employeeId}/attendance/${date}/correction`, { status, reason })
      toast(`${employeeName || 'Employee'} marked ${titleCase(status)} for ${fmtDate(date)}`, 'success')
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Correct past attendance" onClose={onClose} footer={
      <>
        <button className="btn secondary" type="button" onClick={onClose} disabled={busy}>Cancel</button>
        <button className="btn" type="submit" form="attendance-correction" disabled={busy || !employeeId || !date}>
          {busy ? 'Saving…' : 'Save Correction'}
        </button>
      </>
    }>
      <form id="attendance-correction" onSubmit={submit}>
        {!initial && (
          <Field label="Employee" required help={employeeName ? `Selected: ${employeeName}` : 'Search by name, email, or employee code.'}>
            <input className="input" value={employeeSearch} disabled={!!employeeId}
              onChange={(event) => setEmployeeSearch(event.target.value)} placeholder="Search employees…" />
            {!employeeId && matches.length > 0 && (
              <select className="input" size={Math.min(matches.length, 5)} value=""
                onChange={(event) => {
                  const item = matches.find((candidate) => String(candidate.id) === event.target.value)
                  if (item) { setEmployeeId(String(item.id)); setEmployeeName(item.full_name); setMatches([]) }
                }}>
                <option value="" disabled>Select an employee</option>
                {matches.map((item) => <option key={item.id} value={item.id}>{item.full_name} · {item.employee_code} · {item.is_active ? 'Active' : 'Inactive'}</option>)}
              </select>
            )}
            {employeeId && <button type="button" className="btn ghost sm" onClick={() => { setEmployeeId(''); setEmployeeName(''); setEmployeeSearch('') }}>Choose another employee</button>}
          </Field>
        )}
        <div className="form-row">
          <Field label="Work date" required>
            <input className="input" type="date" required max={maxDate}
              value={date} onChange={(event) => setDate(event.target.value)} />
          </Field>
          <Field label="Corrected status" required>
            <select className="input" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="present">Present</option><option value="absent">Absent</option>
            </select>
          </Field>
        </div>
        <Field label="Reason for correction" required help="Required for the audit trail. The employee’s original punch and location evidence will be preserved.">
          <textarea className="input" required minLength={10} maxLength={1000} value={reason}
            onChange={(event) => setReason(event.target.value)} placeholder="Explain why this attendance status needs correction…" />
        </Field>
      </form>
    </Modal>
  )
}

export default function Team() {
  const toast = useToast()
  const { user } = useAuth()
  const [members, setMembers] = useState([])
  const [orgData, setOrgData] = useState(null)
  const [filters, setFilters] = useState({ employee_id: '', department_id: '', status: '', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [correction, setCorrection] = useState(null)
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    api.get('/team/members').then(setMembers).catch(() => {})
    api.get('/admin/org-data').then(setOrgData).catch(() => {})
  }, [])

  useEffect(() => {
    setData(null)
    const params = new URLSearchParams({ page, page_size: 25 })
    Object.entries(filters).forEach(([k, v]) => v && params.append(k, v))
    api.get(`/team/attendance?${params}`).then(setData).catch((e) => toast(e.message, 'error'))
  }, [filters, page, toast, reloadToken])

  const setF = (k, v) => { setFilters((f) => ({ ...f, [k]: v })); setPage(1) }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card pad toolbar">
        <select className="input" style={{ width: 180 }} value={filters.employee_id}
                onChange={(e) => setF('employee_id', e.target.value)}>
          <option value="">All employees</option>
          {members.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}
        </select>
        <select className="input" style={{ width: 160 }} value={filters.department_id}
                onChange={(e) => setF('department_id', e.target.value)}>
          <option value="">All departments</option>
          {(orgData?.departments || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select className="input" style={{ width: 140 }} value={filters.status}
                onChange={(e) => setF('status', e.target.value)}>
          <option value="">Any status</option>
          {['present', 'half_day', 'absent', 'leave', 'wfh', 'holiday'].map((s) =>
            <option key={s} value={s}>{s === 'wfh' ? 'WFH' : s.replaceAll('_', ' ')}</option>)}
        </select>
        <input className="input" style={{ width: 150 }} type="date" value={filters.date_from}
               onChange={(e) => setF('date_from', e.target.value)} aria-label="From date" />
        <input className="input" style={{ width: 150 }} type="date" value={filters.date_to}
               onChange={(e) => setF('date_to', e.target.value)} aria-label="To date" />
        {user.role === 'admin' && <button className="btn" onClick={() => setCorrection({})}>Correct past attendance</button>}
      </div>

      <div className="card">
        {data === null ? <Spinner /> : data.items.length === 0
          ? <EmptyState icon={Users} title="No attendance records match"
                        hint="Try adjusting the filters above." />
          : (
            <>
              <div className="table-wrap"><table className="table">
                <thead><tr><th>Employee</th><th>Date</th><th>Check In</th><th>Check Out</th>
                  <th className="num">Hours</th><th className="num">Break</th><th>Status</th><th>Late</th>
                  {user.role === 'admin' && <><th>Correction</th><th>Action</th></>}</tr></thead>
                <tbody>
                  {data.items.map((a) => (
                    <tr key={a.id}>
                      <td><strong>{a.user.full_name}</strong>
                        <div className="help-text">{a.user.department || ''}</div></td>
                      <td>{fmtDate(a.date)}</td>
                      <td>{fmtTime(a.check_in)}</td>
                      <td>{fmtTime(a.check_out)}</td>
                      <td className="num">{fmtHours(a.work_hours)}</td>
                      <td className="num">{Math.round(a.break_minutes)}m</td>
                      <td><StatusBadge status={a.status} /></td>
                      <td>{a.is_late ? <span className="badge danger">Late</span> : '—'}</td>
                      {user.role === 'admin' && <>
                        <td>{a.status_override ? <>
                          <span>{titleCase(a.status_override)} by {a.status_override_by || 'Admin'}</span>
                          {a.status_override_at && <div className="help-text">{fmtDateTime(a.status_override_at)}</div>}
                          {a.status_override_reason && <div className="help-text">{a.status_override_reason}</div>}
                        </> : '—'}</td>
                        <td><button className="btn secondary sm" onClick={() => setCorrection(a)}>Correct</button></td>
                      </>}
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </>
          )}
      </div>
      {correction && <AttendanceCorrectionModal initial={correction.user ? correction : null}
        onClose={() => setCorrection(null)} onDone={() => { setCorrection(null); setReloadToken((n) => n + 1); }} />}
    </div>
  )
}
