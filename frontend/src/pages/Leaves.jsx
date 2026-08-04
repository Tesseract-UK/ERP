// Leave management: balances, apply, history, cancel.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  ConfirmDialog, EmptyState, Modal, Spinner, StatusBadge,
  fmtDate, titleCase, useToast,
} from '../components/ui'
import { Plane } from '../components/icons'
import { LeaveApplyForm } from '../components/RequestForms'

export default function Leaves() {
  const toast = useToast()
  const [rows, setRows] = useState(null)
  const [balances, setBalances] = useState(null)
  const [showApply, setShowApply] = useState(false)
  const [cancelId, setCancelId] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.get('/leaves').then(setRows).catch((e) => toast(e.message, 'error'))
    api.get('/leaves/balance').then(setBalances).catch(() => {})
  }, [toast])
  useEffect(load, [load])

  const cancel = async () => {
    setBusy(true)
    try {
      await api.post(`/leaves/${cancelId}/cancel`)
      toast('Leave request cancelled', 'success')
      setCancelId(null)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h2>Leaves</h2><div className="sub">Apply for leave and track approvals</div></div>
        <button className="btn" onClick={() => setShowApply(true)}>+ Apply for Leave</button>
      </div>

      {balances && (
        <div className="grid cols-4">
          {['casual', 'sick', 'earned', 'optional_holiday'].map((t) => (
            <div className="card stat" key={t}>
              <div className="label">{titleCase(t)}</div>
              <div className="value">{balances[t].remaining}</div>
              <div className="sub">used {balances[t].used} of {balances[t].allocated}</div>
            </div>
          ))}
        </div>
      )}

      <div className="card">
        <div className="card-head"><h3>Leave History</h3></div>
        {rows === null ? <Spinner /> : rows.length === 0
          ? <EmptyState icon={Plane} title="No leave requests yet" hint="Your leave history will appear here." />
          : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Type</th><th>Dates</th><th className="num">Days</th><th>Reason</th>
                <th>Status</th><th>Reviewed By</th><th></th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{titleCase(r.leave_type)}</td>
                    <td>{fmtDate(r.start_date)} → {fmtDate(r.end_date)}</td>
                    <td className="num">{r.days}</td>
                    <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.reason}>{r.reason}</td>
                    <td><StatusBadge status={r.status} />
                      {r.approver_comment && <div className="help-text" title={r.approver_comment}>“{r.approver_comment}”</div>}</td>
                    <td>{r.approver_name || '—'}</td>
                    <td>{r.status === 'pending' &&
                      <button className="btn ghost sm" onClick={() => setCancelId(r.id)}>Cancel</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
      </div>

      {showApply && (
        <Modal title="Apply for Leave" onClose={() => setShowApply(false)}>
          <LeaveApplyForm onCancel={() => setShowApply(false)}
                          onDone={() => { setShowApply(false); load() }} />
        </Modal>
      )}
      {cancelId && <ConfirmDialog title="Cancel leave request" danger busy={busy}
        message="Are you sure you want to cancel this pending leave request?"
        confirmLabel="Yes, cancel it" onConfirm={cancel} onClose={() => setCancelId(null)} />}
    </div>
  )
}
