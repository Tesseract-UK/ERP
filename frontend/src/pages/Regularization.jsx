// Attendance regularization: fix missed check-ins/outs, pending manager approval.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  EmptyState, Field, Modal, Spinner, StatusBadge, fmtDate, fmtTime, useToast,
} from '../components/ui'

function ApplyModal({ onClose, onDone }) {
  const toast = useToast()
  const [form, setForm] = useState({ date: '', check_in: '', check_out: '', reason: '' })
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const today = new Date().toISOString().slice(0, 10)

  const submit = async (e) => {
    e.preventDefault()
    if (!form.check_in && !form.check_out) {
      toast('Enter a corrected check-in and/or check-out time', 'error')
      return
    }
    setBusy(true)
    try {
      await api.post('/regularization', {
        date: form.date,
        requested_check_in: form.check_in ? `${form.date}T${form.check_in}:00` : null,
        requested_check_out: form.check_out ? `${form.date}T${form.check_out}:00` : null,
        reason: form.reason,
      })
      toast('Regularization request submitted for approval', 'success')
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Regularize Attendance" onClose={onClose} footer={
      <>
        <button className="btn secondary" onClick={onClose}>Cancel</button>
        <button className="btn" form="reg-form" disabled={busy}>{busy ? 'Submitting…' : 'Submit Request'}</button>
      </>
    }>
      <form id="reg-form" onSubmit={submit}>
        <Field label="Date to correct" required>
          <input className="input" type="date" required max={today} value={form.date}
                 onChange={(e) => set('date', e.target.value)} />
        </Field>
        <div className="form-row">
          <Field label="Correct check-in time" help="Leave blank if only fixing check-out">
            <input className="input" type="time" value={form.check_in}
                   onChange={(e) => set('check_in', e.target.value)} />
          </Field>
          <Field label="Correct check-out time" help="Leave blank if only fixing check-in">
            <input className="input" type="time" value={form.check_out}
                   onChange={(e) => set('check_out', e.target.value)} />
          </Field>
        </div>
        <Field label="Reason" required>
          <textarea className="input" required minLength={3} value={form.reason}
                    onChange={(e) => set('reason', e.target.value)}
                    placeholder="e.g. Forgot to check out before leaving the office" />
        </Field>
      </form>
    </Modal>
  )
}

export default function Regularization() {
  const toast = useToast()
  const [rows, setRows] = useState(null)
  const [showApply, setShowApply] = useState(false)

  const load = useCallback(() => {
    api.get('/regularization').then(setRows).catch((e) => toast(e.message, 'error'))
  }, [toast])
  useEffect(load, [load])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h2>Attendance Regularization</h2>
          <div className="sub">Forgot to check in or out? Request a correction here.</div></div>
        <button className="btn" onClick={() => setShowApply(true)}>+ New Request</button>
      </div>

      <div className="card">
        {rows === null ? <Spinner /> : rows.length === 0
          ? <EmptyState icon="✎" title="No regularization requests"
                        hint="Corrections you request will appear here with their approval status." />
          : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Date</th><th>Requested In</th><th>Requested Out</th>
                <th>Reason</th><th>Status</th><th>Reviewed By</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{fmtDate(r.date)}</td>
                    <td>{fmtTime(r.requested_check_in)}</td>
                    <td>{fmtTime(r.requested_check_out)}</td>
                    <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.reason}>{r.reason}</td>
                    <td><StatusBadge status={r.status} />
                      {r.approver_comment && <div className="help-text">“{r.approver_comment}”</div>}</td>
                    <td>{r.approver_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
      </div>

      {showApply && <ApplyModal onClose={() => setShowApply(false)}
                                onDone={() => { setShowApply(false); load() }} />}
    </div>
  )
}
