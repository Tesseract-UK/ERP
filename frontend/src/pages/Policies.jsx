// HR/Admin: leave & WFH allocations, plus the company calendar. Click any date
// on the calendar to add a holiday there; Admins can also declare a
// company-wide work-from-home day. Both are announced to everyone.
import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import {
  ConfirmDialog, Field, Modal, NumberInput, Spinner, fmtDate, localDateStr, titleCase, useToast,
} from '../components/ui'
import { MonthNav } from '../components/MonthCalendar'

const POLICY_KEYS = ['casual', 'sick', 'earned', 'maternity', 'paternity', 'optional_holiday', 'wfh']
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

function AddDayModal({ date, isAdmin, onClose, onDone }) {
  const toast = useToast()
  const [mode, setMode] = useState('holiday')
  const [form, setForm] = useState({ name: '', holiday_type: 'company', note: '' })
  const [busy, setBusy] = useState(false)
  const weekend = [0, 6].includes(new Date(`${date}T00:00`).getDay())

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      if (mode === 'holiday') {
        await api.post('/hr/holidays', { date, name: form.name, holiday_type: form.holiday_type })
        toast('Holiday added and announced', 'success')
      } else {
        await api.post('/company-calendar/wfh-days', { date, note: form.note || 'Company-wide work from home' })
        toast('Company WFH day declared and announced', 'success')
      }
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={new Date(`${date}T00:00`).toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
           onClose={onClose} footer={
      <>
        <button className="btn secondary" onClick={onClose}>Cancel</button>
        <button className="btn" form="day-form" disabled={busy}>{busy ? 'Saving…' : mode === 'holiday' ? 'Add holiday' : 'Declare company WFH'}</button>
      </>
    }>
      <form id="day-form" onSubmit={submit}>
        {isAdmin && (
          <Field label="Mark this date as">
            <div className="segmented">
              <button type="button" className={`seg leave${mode === 'holiday' ? ' active' : ''}`} onClick={() => setMode('holiday')}>Holiday</button>
              <button type="button" className={`seg wfh${mode === 'wfh' ? ' active' : ''}`} disabled={weekend}
                      onClick={() => setMode('wfh')}>Company-wide WFH</button>
            </div>
          </Field>
        )}
        {mode === 'holiday' ? <>
          <Field label="Holiday name" required>
            <input className="input" required autoFocus value={form.name}
                   onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </Field>
          <Field label="Type">
            <select className="input" value={form.holiday_type}
                    onChange={(e) => setForm({ ...form, holiday_type: e.target.value })}>
              {['national', 'state', 'company', 'optional'].map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
            </select>
          </Field>
        </> : (
          <Field label="Note for everyone" help="Posted as an announcement. No one needs to apply, and it doesn't use WFH balance.">
            <input className="input" maxLength={200} value={form.note} placeholder="e.g. Office maintenance"
                   onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </Field>
        )}
        <p className="help-text">Everyone in the company is notified via Announcements.</p>
      </form>
    </Modal>
  )
}

function CompanyCalendar({ isAdmin }) {
  const toast = useToast()
  const now = new Date()
  const [ym, setYm] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 })
  const [cal, setCal] = useState(null)
  const [adding, setAdding] = useState(null)
  const [removing, setRemoving] = useState(null) // { kind: 'holiday'|'wfh', item }
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.get(`/company-calendar?year=${ym.year}`).then(setCal).catch((e) => toast(e.message, 'error'))
  }, [ym.year, toast])
  useEffect(load, [load])

  const byDate = useMemo(() => {
    const map = {}
    for (const h of cal?.holidays || []) map[h.date] = { kind: 'holiday', item: h }
    for (const w of cal?.wfh_days || []) map[w.date] = { kind: 'wfh', item: w }
    return map
  }, [cal])

  const remove = async () => {
    setBusy(true)
    try {
      if (removing.kind === 'holiday') await api.del(`/hr/holidays/${removing.item.id}`)
      else await api.del(`/company-calendar/wfh-days/${removing.item.id}`)
      toast('Removed from the calendar', 'success')
      setRemoving(null)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!cal) return <Spinner />
  const days = new Date(ym.year, ym.month, 0).getDate()
  const firstDow = new Date(ym.year, ym.month - 1, 1).getDay()
  const prefix = `${ym.year}-${String(ym.month).padStart(2, '0')}`
  const todayIso = localDateStr(new Date())
  const monthEntries = Object.entries(byDate).filter(([d]) => d.startsWith(prefix)).sort(([a], [b]) => a.localeCompare(b))

  return (
    <>
      <div className="card-head">
        <h3>Company Calendar</h3>
        <MonthNav year={ym.year} month={ym.month} onChange={(year, month) => setYm({ year, month })} />
      </div>
      <div className="card-body">
        <div className="cal-grid">
          {DOW.map((d) => <div key={d} className="cal-dow">{d}</div>)}
          {Array.from({ length: firstDow }).map((_, i) => <div key={`e${i}`} className="cal-cell empty" />)}
          {Array.from({ length: days }).map((_, i) => {
            const date = `${prefix}-${String(i + 1).padStart(2, '0')}`
            const entry = byDate[date]
            const weekend = [0, 6].includes(new Date(`${date}T00:00`).getDay())
            const cls = entry ? (entry.kind === 'wfh' ? ' st-wfh' : ' st-holiday') : weekend ? ' st-weekend' : ''
            return (
              <button key={date} className={`cal-cell${cls}${date === todayIso ? ' today' : ''}`}
                      title={entry ? (entry.item.name || entry.item.note) : 'Click to add'}
                      onClick={() => (entry ? setRemoving(entry) : setAdding(date))}>
                <span className="day">{i + 1}</span>
                {entry && <span className="tag">{entry.kind === 'wfh' ? 'WFH' : 'H'}</span>}
              </button>
            )
          })}
        </div>
        <div className="cal-legend">
          <span><span className="chip cal-cell st-holiday" style={{ minHeight: 0, padding: 0 }} />Holiday</span>
          <span><span className="chip cal-cell st-wfh" style={{ minHeight: 0, padding: 0 }} />Company WFH</span>
        </div>
        <p className="help-text" style={{ marginTop: 10 }}>
          Click an empty date to add a holiday{isAdmin ? ' or declare company-wide WFH' : ''}; click a marked date to remove it.
        </p>
        {monthEntries.length > 0 && (
          <div className="table-wrap" style={{ marginTop: 12 }}><table className="table">
            <tbody>
              {monthEntries.map(([date, e]) => (
                <tr key={date}>
                  <td>{fmtDate(date)}</td>
                  <td><strong>{e.item.name || e.item.note}</strong></td>
                  <td>{e.kind === 'wfh' ? <span className="badge wfh">Company WFH</span>
                    : <span className="badge neutral">{titleCase(e.item.holiday_type)}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </div>
      {adding && <AddDayModal date={adding} isAdmin={isAdmin} onClose={() => setAdding(null)}
                              onDone={() => { setAdding(null); load() }} />}
      {removing && (removing.kind === 'wfh' && !isAdmin
        ? <Modal title="Company WFH day" onClose={() => setRemoving(null)}>
            <p>{fmtDate(removing.item.date)} — {removing.item.note}</p>
            <p className="help-text" style={{ marginTop: 8 }}>Only an Admin can change company WFH days.</p>
          </Modal>
        : <ConfirmDialog danger busy={busy}
            title={removing.kind === 'wfh' ? 'Remove company WFH day' : 'Remove holiday'}
            message={`Remove "${removing.item.name || removing.item.note}" on ${fmtDate(removing.item.date)}? Everyone will be notified.`}
            confirmLabel="Remove" onConfirm={remove} onClose={() => setRemoving(null)} />)}
    </>
  )
}

export default function Policies() {
  const toast = useToast()
  const { user } = useAuth()
  const [policies, setPolicies] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/hr/policies').then(setPolicies).catch((e) => toast(e.message, 'error'))
  }, [toast])

  const savePolicies = async () => {
    setBusy(true)
    try {
      await api.put('/hr/policies', { allocations: policies })
      toast('Leave policy updated', 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid cols-2" style={{ alignItems: 'start' }}>
      <div className="card">
        <div className="card-head"><h3>Standard Annual Allocations</h3>
          <button className="btn sm" onClick={savePolicies} disabled={busy || !policies}>
            {busy ? 'Saving…' : 'Save Policy'}</button></div>
        <div className="card-body">
          {policies === null ? <Spinner /> : POLICY_KEYS.map((k) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
              <span>{k === 'wfh' ? 'Work From Home (annual cap)' : `${titleCase(k)} Leave`}</span>
              <NumberInput style={{ width: 90 }} min={0} max={365} value={policies[k] ?? 0}
                           onChange={(n) => setPolicies({ ...policies, [k]: n ?? 0 })} />
            </div>
          ))}
          <p className="help-text" style={{ marginTop: 10 }}>
            These are the standard numbers HR can copy onto an employee (Employee → Leave &amp; WFH
            Allocations → “Fill from company policy”). They are not applied automatically: every
            employee’s balance is 0 until HR sets it.
            Unpaid leave is always unlimited. WFH accrues monthly (this annual number ÷ 12
            per month) rather than being granted all at once, and can go negative if overused.
            New joiners have no balance until HR assigns their reporting manager.
          </p>
        </div>
      </div>
      <div className="card"><CompanyCalendar isAdmin={user.role === 'admin'} /></div>
    </div>
  )
}
