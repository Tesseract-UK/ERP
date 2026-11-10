// Color-coded month calendar with day-detail modal. Used for both the
// employee's own attendance and manager team views. When `selfService` is
// set (Attendance page only), clicking a date also offers quick Leave/WFH
// application for that date, and shows any existing request for it.
import { useState } from 'react'
import { useAuth } from '../AuthContext'
import {
  Modal, StatusBadge, fmtDateTime, fmtHours, fmtTime, localDateStr, titleCase,
} from './ui'
import { ChevronLeft, ChevronRight } from './icons'
import { ApplyRequestForm, KindBadge } from './RequestForms'

const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const LEGEND = [
  ['st-present', 'Present'], ['st-wfh', 'Work From Home'], ['st-leave', 'Leave'], ['st-half_day', 'Half Day'],
  ['st-absent', 'Absent'], ['st-holiday', 'Holiday / Weekend'],
]

export function MonthNav({ year, month, onChange }) {
  const shift = (delta) => {
    const d = new Date(year, month - 1 + delta, 1)
    onChange(d.getFullYear(), d.getMonth() + 1)
  }
  return (
    <div className="toolbar">
      <button className="btn secondary sm" onClick={() => shift(-1)} aria-label="Previous month"><ChevronLeft size={15} /></button>
      <strong style={{ minWidth: 130, textAlign: 'center' }}>
        {new Date(year, month - 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
      </strong>
      <button className="btn secondary sm" onClick={() => shift(1)} aria-label="Next month"><ChevronRight size={15} /></button>
    </div>
  )
}

function DayDetail({ cell, selfService, requests, onChanged, onClose }) {
  const { user } = useAuth()
  const [mode, setMode] = useState('view') // 'view' | 'leave' | 'wfh'
  const d = cell.detail
  const isAttendance = d && d.check_in !== undefined
  const title = new Date(cell.date + 'T00:00')
    .toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })

  if (mode !== 'view') {
    return (
      <Modal title="Apply for Leave or WFH" onClose={onClose}>
        <ApplyRequestForm initialType={mode} initialStart={cell.date} initialEnd={cell.date}
                          onCancel={() => setMode('view')}
                          onDone={() => { onChanged?.(); onClose() }} />
      </Modal>
    )
  }

  const dayRequests = selfService
    ? (requests || []).filter((r) => ['pending', 'approved'].includes(r.status)
        && cell.date >= r.start_date && cell.date <= r.end_date)
    : []
  const companyWfh = Boolean(d?.company_wfh)
  const canApply = selfService && cell.status !== 'holiday' && cell.status !== 'weekend' && !companyWfh

  return (
    <Modal title={title} onClose={onClose}>
      <div style={{ marginBottom: 12 }}><StatusBadge status={cell.status || 'absent'} /></div>
      {isAttendance ? (
        <table className="table"><tbody>
          <tr><td>Login time</td><td className="num"><strong>{fmtTime(d.check_in)}</strong></td></tr>
          <tr><td>Logout time</td><td className="num"><strong>{fmtTime(d.check_out)}</strong></td></tr>
          {d.latitude != null && <tr><td>Check-in location</td><td className="num">{d.latitude.toFixed(6)}, {d.longitude.toFixed(6)}</td></tr>}
          {d.distance_from_office_meters != null && <tr><td>Check-in distance</td><td className="num">{Math.round(d.distance_from_office_meters)} m from office</td></tr>}
          {d.checkout_latitude != null && <tr><td>Check-out location</td><td className="num">{d.checkout_latitude.toFixed(6)}, {d.checkout_longitude.toFixed(6)}</td></tr>}
          {d.checkout_distance_from_office_meters != null && <tr><td>Check-out distance</td><td className="num">{Math.round(d.checkout_distance_from_office_meters)} m from office</td></tr>}
          <tr><td>Working hours</td><td className="num"><strong>{fmtHours(d.work_hours)}</strong></td></tr>
          <tr><td>Break duration</td><td className="num"><strong>{Math.round(d.break_minutes)}m ({d.breaks.length} break{d.breaks.length === 1 ? '' : 's'})</strong></td></tr>
          <tr><td>Overtime</td><td className="num"><strong>{d.overtime_hours > 0 ? fmtHours(d.overtime_hours) : '—'}</strong></td></tr>
          <tr><td>Late arrival</td><td className="num"><strong>{d.is_late ? 'Yes' : 'No'}</strong></td></tr>
          {d.status_override && <>
            <tr><td>Admin correction</td><td className="num"><strong>{titleCase(d.status_override)}</strong></td></tr>
            {d.status_override_by && <tr><td>Changed by</td><td className="num">{d.status_override_by}</td></tr>}
            {d.status_override_at && <tr><td>Changed at</td><td className="num">{fmtDateTime(d.status_override_at)}</td></tr>}
            {d.status_override_reason && <tr><td>Reason</td><td className="num">{d.status_override_reason}</td></tr>}
          </>}
          {d.notes && <tr><td>Notes</td><td className="num">{d.notes}</td></tr>}
        </tbody></table>
      ) : (
        <p style={{ color: 'var(--ink-2)' }}>
          {cell.status === 'holiday' && d?.name ? `Holiday: ${d.name}`
            : cell.status === 'leave' && d?.leave_type ? `On ${titleCase(d.leave_type)} leave`
            : companyWfh ? `Company-wide work from home${d.name ? ` — ${d.name}` : ''}`
            : cell.status === 'wfh' ? 'Approved work-from-home day'
            : cell.status === 'weekend' ? 'Weekend'
            : 'No attendance record for this day.'}
        </p>
      )}

      {canApply && (
        <div style={{ marginTop: 16, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
          {dayRequests.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {dayRequests.map((r) => (
                <div key={`${r.kind}-${r.id}`}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}><KindBadge kind={r.kind} />
                      {r.kind === 'leave' && <strong>{titleCase(r.leave_type)}</strong>}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  {r.reason && <div className="help-text">“{r.reason}”</div>}
                  {r.approver_name && r.status !== 'pending' &&
                    <div className="help-text">Reviewed by {r.approver_name}</div>}
                </div>
              ))}
            </div>
          ) : user?.can_request ? (
            <div className="toolbar">
              <button type="button" className="btn secondary sm" onClick={() => setMode('leave')}>Apply for Leave</button>
              <button type="button" className="btn secondary sm" onClick={() => setMode('wfh')}>Request WFH</button>
            </div>
          ) : (
            <p className="help-text">Requests unlock once HR assigns your reporting manager.</p>
          )}
        </div>
      )}
    </Modal>
  )
}

export default function MonthCalendar({ data, selfService, requests, onChanged }) {
  const [selected, setSelected] = useState(null)
  if (!data) return null
  const firstDow = new Date(data.year, data.month - 1, 1).getDay()
  const todayIso = localDateStr(new Date())

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
      {selected && <DayDetail cell={selected} selfService={selfService} requests={requests}
                              onChanged={onChanged} onClose={() => setSelected(null)} />}
    </>
  )
}
