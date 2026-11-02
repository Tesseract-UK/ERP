// HR reports with CSV export.
import { useEffect, useState } from 'react'
import { api, downloadCsv, localNowIso } from '../api'
import { EmptyState, Spinner, fmtDate, useToast } from '../components/ui'
import { BarChart3, Download } from '../components/icons'

const now = new Date()
const REPORTS = [
  { id: 'attendance', label: 'Monthly Attendance', monthly: true },
  { id: 'leaves', label: 'Leave Utilization', monthly: false },
  { id: 'late-arrivals', label: 'Late Arrivals', monthly: true },
]

export default function Reports() {
  const toast = useToast()
  const [report, setReport] = useState('attendance')
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [departments, setDepartments] = useState([])
  const [departmentId, setDepartmentId] = useState('')
  const [rows, setRows] = useState(null)
  const [detailFrom, setDetailFrom] = useState(`${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`)
  const [detailTo, setDetailTo] = useState(localNowIso().slice(0, 10))
  const [employeeSearch, setEmployeeSearch] = useState('')
  const [employeeOptions, setEmployeeOptions] = useState([])
  const [selectedEmployee, setSelectedEmployee] = useState(null)
  const [detailBusy, setDetailBusy] = useState(false)

  const cfg = REPORTS.find((r) => r.id === report)
  const query = () => {
    const p = new URLSearchParams({ year })
    if (cfg.monthly) p.append('month', month)
    if (report === 'attendance' && departmentId) p.append('department_id', departmentId)
    return p
  }

  useEffect(() => {
    api.get('/admin/org-data').then((d) => setDepartments(d.departments)).catch(() => {})
  }, [])

  useEffect(() => {
    const term = employeeSearch.trim()
    if (term.length < 2) { setEmployeeOptions([]); return undefined }
    let active = true
    const timer = window.setTimeout(() => {
      api.get(`/hr/employees?${new URLSearchParams({ search: term, page_size: 30 })}`)
        .then((result) => { if (active) setEmployeeOptions(result.items || []) })
        .catch((error) => { if (active) toast(error.message, 'error') })
    }, 250)
    return () => { active = false; window.clearTimeout(timer) }
  }, [employeeSearch, toast])

  useEffect(() => {
    setRows(null)
    api.get(`/hr/reports/${report}?${query()}`)
      .then(setRows).catch((e) => toast(e.message, 'error'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report, year, month, departmentId])

  const exportCsv = () => {
    const p = query(); p.append('format', 'csv')
    downloadCsv(`/hr/reports/${report}?${p}`, `${report}_${year}${cfg.monthly ? '_' + String(month).padStart(2, '0') : ''}.csv`)
      .catch((e) => toast(e.message, 'error'))
  }

  const exportDetailedAttendance = async () => {
    if (!detailFrom || !detailTo || detailFrom > detailTo) {
      toast('Choose a valid date range', 'error')
      return
    }
    setDetailBusy(true)
    const params = new URLSearchParams({ date_from: detailFrom, date_to: detailTo })
    if (selectedEmployee) params.set('employee_id', selectedEmployee.id)
    const scope = selectedEmployee ? selectedEmployee.employee_code : 'all_staff'
    try {
      await downloadCsv(
        `/hr/reports/attendance-detail?${params}`,
        `attendance_${scope}_${detailFrom}_${detailTo}.csv`,
      )
      toast('Detailed attendance CSV downloaded', 'success')
    } catch (error) { toast(error.message, 'error') }
    finally { setDetailBusy(false) }
  }

  const headers = rows?.length ? Object.keys(rows[0]) : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <section className="card pad">
        <div style={{ marginBottom: 12 }}><h3>Detailed Attendance Export</h3>
          <div className="sub">Daily punches, leave/WFH/absence status, work hours, and employee totals. Maximum range: one year.</div></div>
        <div className="toolbar" style={{ alignItems: 'end', flexWrap: 'wrap' }}>
          <label className="field"><span className="label">From</span>
            <input className="input" type="date" value={detailFrom} max={detailTo || undefined}
              onChange={(event) => setDetailFrom(event.target.value)} /></label>
          <label className="field"><span className="label">To</span>
            <input className="input" type="date" value={detailTo} min={detailFrom || undefined}
              onChange={(event) => setDetailTo(event.target.value)} /></label>
          <div className="field" style={{ position: 'relative', minWidth: 240, flex: 1 }}>
            <span className="label">Employee (optional)</span>
            {selectedEmployee ? <div className="input" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{selectedEmployee.full_name} · {selectedEmployee.employee_code}</span>
              <button type="button" className="btn ghost sm" onClick={() => setSelectedEmployee(null)}>All staff</button>
            </div> : <input className="input" value={employeeSearch} placeholder="Search name or employee code"
              onChange={(event) => setEmployeeSearch(event.target.value)} />}
            {!selectedEmployee && employeeOptions.length > 0 && <div role="listbox" className="card" style={{ position: 'absolute', zIndex: 10, top: '100%', left: 0, right: 0, maxHeight: 220, overflowY: 'auto' }}>
              {employeeOptions.map((employee) => <button key={employee.id} type="button" role="option" className="btn ghost sm"
                style={{ display: 'block', width: '100%', textAlign: 'left', padding: 9 }}
                onClick={() => { setSelectedEmployee(employee); setEmployeeSearch(''); setEmployeeOptions([]) }}>
                {employee.full_name} · {employee.employee_code}
              </button>)}
            </div>}
          </div>
          <button className="btn" disabled={detailBusy || !detailFrom || !detailTo} onClick={exportDetailedAttendance}>
            <Download size={14} /> {detailBusy ? 'Preparing…' : 'Export Daily Sheet'}
          </button>
        </div>
        <p className="help-text" style={{ marginTop: 10 }}>Leave Employee blank to export all active employees. The file contains daily rows followed by a summary row for each employee.</p>
      </section>

      <div className="card pad toolbar">
        <select className="input" style={{ width: 200 }} value={report} onChange={(e) => setReport(e.target.value)}>
          {REPORTS.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
        </select>
        <select className="input" style={{ width: 100 }} value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {[year - 2, year - 1, year, year + 1].filter((v, i, a) => a.indexOf(v) === i).map((y) =>
            <option key={y} value={y}>{y}</option>)}
        </select>
        {cfg.monthly && (
          <select className="input" style={{ width: 130 }} value={month} onChange={(e) => setMonth(Number(e.target.value))}>
            {Array.from({ length: 12 }, (_, i) => (
              <option key={i + 1} value={i + 1}>
                {new Date(2000, i).toLocaleDateString(undefined, { month: 'long' })}
              </option>
            ))}
          </select>
        )}
        {report === 'attendance' && (
          <select className="input" style={{ width: 170 }} value={departmentId}
                  onChange={(e) => setDepartmentId(e.target.value)}>
            <option value="">All departments</option>
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
        )}
        <div style={{ flex: 1 }} />
        <button className="btn secondary" onClick={exportCsv} disabled={rows === null}>
          <Download size={14} /> Export CSV</button>
      </div>

      <div className="card">
        {rows === null ? <Spinner /> : rows.length === 0
          ? <EmptyState icon={BarChart3} title="No data for this period" hint="Try another month or report." />
          : (
            <div className="table-wrap"><table className="table">
              <thead><tr>{headers.map((h) => (
                <th key={h} className={typeof rows[0][h] === 'number' ? 'num' : ''}>
                  {h.replaceAll('_', ' ')}</th>))}</tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>{headers.map((h) => (
                    <td key={h} className={typeof r[h] === 'number' ? 'num' : ''}>
                      {h === 'date' ? fmtDate(r[h]) : String(r[h] ?? '—')}</td>))}</tr>
                ))}
              </tbody>
            </table></div>
          )}
      </div>
    </div>
  )
}
