// Shared Leave / WFH application forms — used by the Leaves and WFH pages,
// and by the Attendance calendar's per-date quick-apply flow.
import { useEffect, useState } from 'react'
import { api } from '../api'
import { Field, titleCase, useToast } from './ui'

const LEAVE_TYPES = ['casual', 'sick', 'earned', 'unpaid', 'maternity', 'paternity', 'optional_holiday']

const FormFoot = ({ busy, onCancel, label = 'Submit Request' }) => (
  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
    <button type="button" className="btn secondary" onClick={onCancel} disabled={busy}>Cancel</button>
    <button className="btn" disabled={busy}>{busy ? 'Submitting…' : label}</button>
  </div>
)

export function LeaveApplyForm({ initialStart = '', initialEnd = '', onDone, onCancel }) {
  const toast = useToast()
  const [balances, setBalances] = useState(null)
  const [form, setForm] = useState({
    leave_type: 'casual', start_date: initialStart, end_date: initialEnd || initialStart, reason: '',
  })
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  useEffect(() => { api.get('/leaves/balance').then(setBalances).catch(() => {}) }, [])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const fd = new FormData()
      Object.entries(form).forEach(([k, v]) => fd.append(k, v))
      if (file) fd.append('document', file)
      await api.postForm('/leaves', fd)
      toast('Leave request submitted for approval', 'success')
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <Field label="Leave type" required help={balances && form.leave_type !== 'unpaid'
        ? `${balances[form.leave_type]?.remaining ?? 0} day(s) remaining` : undefined}>
        <select className="input" value={form.leave_type} onChange={(e) => set('leave_type', e.target.value)}>
          {LEAVE_TYPES.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
        </select>
      </Field>
      <div className="form-row">
        <Field label="From date" required>
          <input className="input" type="date" required value={form.start_date}
                 onChange={(e) => set('start_date', e.target.value)} />
        </Field>
        <Field label="To date" required help="Inclusive of both dates">
          <input className="input" type="date" required value={form.end_date} min={form.start_date}
                 onChange={(e) => set('end_date', e.target.value)} />
        </Field>
      </div>
      <Field label="Reason" required>
        <textarea className="input" required minLength={3} value={form.reason}
                  onChange={(e) => set('reason', e.target.value)}
                  placeholder="Briefly describe the reason for your leave" />
      </Field>
      <Field label="Supporting document (optional)" help="PDF, image or Word document up to 5 MB">
        <input className="input" type="file" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
               onChange={(e) => setFile(e.target.files[0])} />
      </Field>
      <FormFoot busy={busy} onCancel={onCancel} />
    </form>
  )
}

export function WfhApplyForm({ initialStart = '', initialEnd = '', onDone, onCancel }) {
  const toast = useToast()
  const [form, setForm] = useState({ start_date: initialStart, end_date: initialEnd || initialStart, reason: '' })
  const [file, setFile] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const start = new Date(`${form.start_date}T00:00`)
      const end = new Date(`${form.end_date}T00:00`)
      if (end < start) throw new Error('To date must be on or after the from date')
      const dates = []
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        if (d.getDay() !== 0 && d.getDay() !== 6) dates.push(d.toISOString().slice(0, 10))
      }
      if (!dates.length) throw new Error('Selected range contains no weekdays')

      let ok = 0
      const failures = []
      for (const d of dates) {
        const fd = new FormData()
        fd.append('date', d)
        fd.append('reason', form.reason)
        if (file) fd.append('document', file)
        try {
          await api.postForm('/wfh', fd)
          ok++
        } catch (err) {
          failures.push(`${d}: ${err.message}`)
        }
      }
      if (ok) {
        toast(`WFH requested for ${ok} day${ok === 1 ? '' : 's'}${failures.length ? ` — ${failures.length} skipped` : ''}`,
              failures.length ? 'error' : 'success')
        onDone()
      } else {
        toast(failures[0] || 'Could not submit WFH request', 'error')
      }
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <div className="form-row">
        <Field label="From date" required>
          <input className="input" type="date" required value={form.start_date}
                 onChange={(e) => set('start_date', e.target.value)} />
        </Field>
        <Field label="To date" required help="Inclusive — weekends are skipped automatically">
          <input className="input" type="date" required value={form.end_date} min={form.start_date}
                 onChange={(e) => set('end_date', e.target.value)} />
        </Field>
      </div>
      <Field label="Reason" required>
        <textarea className="input" required minLength={3} value={form.reason}
                  onChange={(e) => set('reason', e.target.value)}
                  placeholder="Why do you need to work from home?" />
      </Field>
      <Field label="Supporting document (optional)">
        <input className="input" type="file" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
               onChange={(e) => setFile(e.target.files[0])} />
      </Field>
      <FormFoot busy={busy} onCancel={onCancel} />
    </form>
  )
}
