// Color-coded month calendar with day-detail modal. Used for both the
// employee's own attendance and manager team views.
import { useState } from 'react'
import {
  Modal, StatusBadge, fmtHours, fmtTime, titleCase,
} from './ui'

const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const LEGEND = [
  ['st-present', 'Present'], ['st-wfh', 'Work From Home'], ['st-leave', 'Leave / Half Day'],
  ['st-absent', 'Absent'], ['st-holiday', 'Holiday / Weekend'],
]

export function MonthNav({ year, month, onChange }) {
  const shift = (delta) => {
    const d = new Date(year, month - 1 + delta, 1)
    onChange(d.getFullYear(), d.getMonth() + 1)
  }
  return (
    <div className="toolbar">
      <button className="btn secondary sm" onClick={() => shift(-1)}>←</button>
      <strong style={{ minWidth: 130, textAlign: 'center' }}>
        {new Date(year, month - 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
      </strong>
      <button className="btn secondary sm" onClick={() => shift(1)}>→</button>
    </div>
  )
}

function DayDetail({ cell, onClose }) {
  const d = cell.detail
  const isAttendance = d && d.check_in !== undefined
  return (
    <Modal title={new Date(cell.date + 'T00:00').toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
           onClose={onClose}>
      <div style={{ marginBottom: 12 }}><StatusBadge status={cell.status || 'absent'} /></div>
      {isAttendance ? (
        <table className="table"><tbody>
          <tr><td>Login time</td><td className="num"><strong>{fmtTime(d.check_in)}</strong></td></tr>
          <tr><td>Logout time</td><td className="num"><strong>{fmtTime(d.check_out)}</strong></td></tr>
          <tr><td>Working hours</td><td className="num"><strong>{fmtHours(d.work_hours)}</strong></td></tr>
          <tr><td>Break duration</td><td className="num"><strong>{Math.round(d.break_minutes)}m ({d.breaks.length} break{d.breaks.length === 1 ? '' : 's'})</strong></td></tr>
          <tr><td>Overtime</td><td className="num"><strong>{d.overtime_hours > 0 ? fmtHours(d.overtime_hours) : '—'}</strong></td></tr>
          <tr><td>Late arrival</td><td className="num"><strong>{d.is_late ? 'Yes' : 'No'}</strong></td></tr>
          {d.notes && <tr><td>Notes</td><td className="num">{d.notes}</td></tr>}
        </tbody></table>
      ) : (
        <p style={{ color: 'var(--ink-2)' }}>
          {cell.status === 'holiday' && d?.name ? `Holiday: ${d.name}`
            : cell.status === 'leave' && d?.leave_type ? `On ${titleCase(d.leave_type)} leave`
            : cell.status === 'wfh' ? 'Approved work-from-home day'
            : cell.status === 'weekend' ? 'Weekend'
            : 'No attendance record for this day.'}
        </p>
      )}
    </Modal>
  )
}

export default function MonthCalendar({ data }) {
  const [selected, setSelected] = useState(null)
  if (!data) return null
  const firstDow = new Date(data.year, data.month - 1, 1).getDay()
  const todayIso = new Date().toISOString().slice(0, 10)

  return (
    <>
      <div className="cal-grid">
        {DOW.map((d) => <div key={d} className="cal-dow">{d}</div>)}
        {Array.from({ length: firstDow }).map((_, i) => <div key={`e${i}`} className="cal-cell empty" />)}
        {data.days.map((cell) => (
          <button key={cell.date}
                  className={`cal-cell${cell.status ? ` st-${cell.status}` : ''}${cell.date === todayIso ? ' today' : ''}`}
                  onClick={() => setSelected(cell)}>
            <span className="day">{Number(cell.date.slice(-2))}</span>
            {cell.status && cell.status !== 'weekend' && (
              <span className="tag">
                {{ present: 'P', wfh: 'WFH', leave: 'L', half_day: '½', absent: 'A', holiday: 'H' }[cell.status] || cell.status}
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="cal-legend">
        {LEGEND.map(([cls, label]) => (
          <span key={cls}><span className={`chip cal-cell ${cls}`} style={{ minHeight: 0, padding: 0 }} />{label}</span>
        ))}
      </div>
      {selected && <DayDetail cell={selected} onClose={() => setSelected(null)} />}
    </>
  )
}
