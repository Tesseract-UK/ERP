// Team attendance with filters and pagination (manager/HR/admin).
import { useEffect, useState } from 'react'
import { api } from '../api'
import {
  EmptyState, Pagination, Spinner, StatusBadge, fmtDate, fmtHours, fmtTime, useToast,
} from '../components/ui'

export default function Team() {
  const toast = useToast()
  const [members, setMembers] = useState([])
  const [orgData, setOrgData] = useState(null)
  const [filters, setFilters] = useState({ employee_id: '', department_id: '', status: '', date_from: '', date_to: '' })
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)

  useEffect(() => {
    api.get('/team/members').then(setMembers).catch(() => {})
    api.get('/admin/org-data').then(setOrgData).catch(() => {})
  }, [])

  useEffect(() => {
    setData(null)
    const params = new URLSearchParams({ page, page_size: 25 })
    Object.entries(filters).forEach(([k, v]) => v && params.append(k, v))
    api.get(`/team/attendance?${params}`).then(setData).catch((e) => toast(e.message, 'error'))
  }, [filters, page, toast])

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
      </div>

      <div className="card">
        {data === null ? <Spinner /> : data.items.length === 0
          ? <EmptyState icon="👥" title="No attendance records match"
                        hint="Try adjusting the filters above." />
          : (
            <>
              <div className="table-wrap"><table className="table">
                <thead><tr><th>Employee</th><th>Date</th><th>Check In</th><th>Check Out</th>
                  <th className="num">Hours</th><th className="num">Break</th><th>Status</th><th>Late</th></tr></thead>
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
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </>
          )}
      </div>
    </div>
  )
}
