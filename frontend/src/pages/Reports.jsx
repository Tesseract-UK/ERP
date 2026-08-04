// HR reports with CSV export.
import { useEffect, useState } from 'react'
import { api, downloadCsv } from '../api'
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

  const headers = rows?.length ? Object.keys(rows[0]) : []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
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
        <button className="btn secondary" onClick={exportCsv} disabled={!rows?.length}>
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
