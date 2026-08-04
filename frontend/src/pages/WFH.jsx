// Work-from-home requests.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  ConfirmDialog, EmptyState, Modal, Spinner, StatusBadge, fmtDate, useToast,
} from '../components/ui'
import { Home } from '../components/icons'
import { WfhApplyForm } from '../components/RequestForms'

export default function WFH() {
  const toast = useToast()
  const [rows, setRows] = useState(null)
  const [balance, setBalance] = useState(null)
  const [showApply, setShowApply] = useState(false)
  const [cancelId, setCancelId] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.get('/wfh').then(setRows).catch((e) => toast(e.message, 'error'))
    api.get('/leaves/balance').then((b) => setBalance(b.wfh)).catch(() => {})
  }, [toast])
  useEffect(load, [load])

  const cancel = async () => {
    setBusy(true)
    try {
      await api.post(`/wfh/${cancelId}/cancel`)
      toast('WFH request cancelled', 'success')
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
        <div><h2>Work From Home</h2><div className="sub">Request and track WFH days</div></div>
        <button className="btn" onClick={() => setShowApply(true)}>+ Request WFH</button>
      </div>

      {balance && (
        <div className="grid cols-4">
          <div className="card stat">
            <div className="label">WFH Remaining</div>
            <div className="value">{balance.remaining}</div>
            <div className="sub">used {balance.used} of {balance.allocated} this year</div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-head"><h3>WFH History</h3></div>
        {rows === null ? <Spinner /> : rows.length === 0
          ? <EmptyState icon={Home} title="No WFH requests yet" hint="Your work-from-home requests will appear here." />
          : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Date</th><th>Reason</th><th>Status</th><th>Reviewed By</th><th></th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{fmtDate(r.date)}</td>
                    <td style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.reason}>{r.reason}</td>
                    <td><StatusBadge status={r.status} />
                      {r.approver_comment && <div className="help-text">“{r.approver_comment}”</div>}</td>
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
        <Modal title="Request Work From Home" onClose={() => setShowApply(false)}>
          <WfhApplyForm onCancel={() => setShowApply(false)}
                        onDone={() => { setShowApply(false); load() }} />
        </Modal>
      )}
      {cancelId && <ConfirmDialog title="Cancel WFH request" danger busy={busy}
        message="Are you sure you want to cancel this pending WFH request?"
        confirmLabel="Yes, cancel it" onConfirm={cancel} onClose={() => setCancelId(null)} />}
    </div>
  )
}
