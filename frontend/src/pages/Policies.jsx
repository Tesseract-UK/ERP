// HR: leave/WFH allocations and holiday calendar.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  ConfirmDialog, EmptyState, Field, Modal, Spinner, fmtDate, titleCase, useToast,
} from '../components/ui'

const POLICY_KEYS = ['casual', 'sick', 'earned', 'maternity', 'paternity', 'optional_holiday', 'wfh']

function HolidayModal({ onClose, onDone }) {
  const toast = useToast()
  const [form, setForm] = useState({ date: '', name: '', holiday_type: 'company' })
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.post('/hr/holidays', form)
      toast('Holiday added', 'success')
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal title="Add Holiday" onClose={onClose} footer={
      <>
        <button className="btn secondary" onClick={onClose}>Cancel</button>
        <button className="btn" form="hol-form" disabled={busy}>{busy ? 'Adding…' : 'Add Holiday'}</button>
      </>
    }>
      <form id="hol-form" onSubmit={submit}>
        <Field label="Date" required>
          <input className="input" type="date" required value={form.date}
                 onChange={(e) => setForm({ ...form, date: e.target.value })} />
        </Field>
        <Field label="Holiday name" required>
          <input className="input" required value={form.name}
                 onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Type">
          <select className="input" value={form.holiday_type}
                  onChange={(e) => setForm({ ...form, holiday_type: e.target.value })}>
            {['national', 'state', 'company', 'optional'].map((t) =>
              <option key={t} value={t}>{titleCase(t)}</option>)}
          </select>
        </Field>
      </form>
    </Modal>
  )
}

export default function Policies() {
  const toast = useToast()
  const [policies, setPolicies] = useState(null)
  const [holidays, setHolidays] = useState(null)
  const [year, setYear] = useState(new Date().getFullYear())
  const [busy, setBusy] = useState(false)
  const [showAdd, setShowAdd] = useState(false)
  const [deleteHoliday, setDeleteHoliday] = useState(null)

  const load = useCallback(() => {
    api.get('/hr/policies').then(setPolicies).catch((e) => toast(e.message, 'error'))
    api.get(`/hr/holidays?year=${year}`).then(setHolidays).catch(() => {})
  }, [year, toast])
  useEffect(load, [load])

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

  const removeHoliday = async () => {
    setBusy(true)
    try {
      await api.del(`/hr/holidays/${deleteHoliday.id}`)
      toast('Holiday removed', 'success')
      setDeleteHoliday(null)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid cols-2" style={{ alignItems: 'start' }}>
      <div className="card">
        <div className="card-head"><h3>Annual Allocations</h3>
          <button className="btn sm" onClick={savePolicies} disabled={busy || !policies}>
            {busy ? 'Saving…' : 'Save Policy'}</button></div>
        <div className="card-body">
          {policies === null ? <Spinner /> : POLICY_KEYS.map((k) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
              <span>{k === 'wfh' ? 'Work From Home (days/year)' : `${titleCase(k)} Leave`}</span>
              <input className="input" type="number" min="0" max="365" style={{ width: 90 }}
                     value={policies[k] ?? 0}
                     onChange={(e) => setPolicies({ ...policies, [k]: Number(e.target.value) })} />
            </div>
          ))}
          <p className="help-text" style={{ marginTop: 10 }}>
            Balances are computed against these allocations for the current calendar year.
            Unpaid leave is always unlimited.
          </p>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3>Holiday Calendar</h3>
          <div className="toolbar">
            <select className="input" style={{ width: 100 }} value={year}
                    onChange={(e) => setYear(Number(e.target.value))}>
              {[year - 1, year, year + 1].map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
            <button className="btn sm" onClick={() => setShowAdd(true)}>+ Add</button>
          </div>
        </div>
        {holidays === null ? <Spinner /> : holidays.length === 0
          ? <EmptyState icon="🗓" title={`No holidays configured for ${year}`} />
          : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Date</th><th>Holiday</th><th>Type</th><th></th></tr></thead>
              <tbody>
                {holidays.map((h) => (
                  <tr key={h.id}>
                    <td>{fmtDate(h.date)}</td>
                    <td><strong>{h.name}</strong></td>
                    <td><span className="badge neutral">{titleCase(h.holiday_type)}</span></td>
                    <td><button className="btn ghost sm" style={{ color: 'var(--danger)' }}
                                onClick={() => setDeleteHoliday(h)}>Remove</button></td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
      </div>

      {showAdd && <HolidayModal onClose={() => setShowAdd(false)}
                                onDone={() => { setShowAdd(false); load() }} />}
      {deleteHoliday && <ConfirmDialog danger busy={busy}
        title="Remove holiday"
        message={`Remove "${deleteHoliday.name}" (${fmtDate(deleteHoliday.date)}) from the calendar?`}
        confirmLabel="Remove" onConfirm={removeHoliday} onClose={() => setDeleteHoliday(null)} />}
    </div>
  )
}
