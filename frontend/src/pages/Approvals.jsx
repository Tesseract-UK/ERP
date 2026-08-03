// Manager/HR approvals inbox for leave, WFH and regularization requests.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  EmptyState, Field, Modal, Spinner, fmtDate, fmtDateTime, fmtTime, titleCase, useToast,
} from '../components/ui'

const KIND_LABEL = { leave: 'Leave', wfh: 'Work From Home', regularization: 'Regularization' }
const KIND_TONE = { leave: 'warn', wfh: 'info', regularization: 'neutral' }

function DecisionModal({ item, decision, onClose, onDone }) {
  const toast = useToast()
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setBusy(true)
    try {
      await api.post(`/approvals/${item.kind}/${item.id}/${decision}`, { comment: comment || null })
      toast(`Request ${decision === 'approve' ? 'approved' : 'rejected'}`, 'success')
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={`${decision === 'approve' ? 'Approve' : 'Reject'} ${KIND_LABEL[item.kind]} request`}
           onClose={onClose} footer={
        <>
          <button className="btn secondary" onClick={onClose} disabled={busy}>Cancel</button>
          <button className={`btn ${decision === 'approve' ? 'success' : 'danger'}`}
                  onClick={submit} disabled={busy}>
            {busy ? 'Working…' : decision === 'approve' ? 'Approve' : 'Reject'}
          </button>
        </>
      }>
      <p style={{ marginBottom: 12 }}>
        <strong>{item.user.full_name}</strong> ({item.user.employee_code}) —{' '}
        {item.kind === 'leave' && <>{titleCase(item.leave_type)} leave, {fmtDate(item.start_date)} → {fmtDate(item.end_date)} ({item.days} day{item.days === 1 ? '' : 's'})</>}
        {item.kind === 'wfh' && <>WFH on {fmtDate(item.date)}</>}
        {item.kind === 'regularization' && <>Correction for {fmtDate(item.date)}: in {fmtTime(item.requested_check_in)}, out {fmtTime(item.requested_check_out)}</>}
      </p>
      <p style={{ color: 'var(--ink-2)', marginBottom: 14 }}>Reason: “{item.reason}”</p>
      <Field label="Comment (optional)" help="Stored with the request for future reference">
        <textarea className="input" value={comment} onChange={(e) => setComment(e.target.value)}
                  placeholder="Add a note for the employee…" />
      </Field>
    </Modal>
  )
}

export default function Approvals() {
  const toast = useToast()
  const [items, setItems] = useState(null)
  const [filter, setFilter] = useState('all')
  const [modal, setModal] = useState(null) // { item, decision }

  const load = useCallback(() => {
    api.get('/approvals/pending').then(setItems).catch((e) => toast(e.message, 'error'))
  }, [toast])
  useEffect(load, [load])

  if (items === null) return <Spinner />
  const visible = filter === 'all' ? items : items.filter((i) => i.kind === filter)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h2>Pending Approvals</h2>
          <div className="sub">{items.length} request{items.length === 1 ? '' : 's'} awaiting your review</div></div>
        <div className="toolbar">
          <select className="input" style={{ width: 'auto' }} value={filter}
                  onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All types</option>
            <option value="leave">Leave</option>
            <option value="wfh">Work From Home</option>
            <option value="regularization">Regularization</option>
          </select>
        </div>
      </div>

      {visible.length === 0
        ? <div className="card"><EmptyState icon="✅" title="All caught up!"
            hint="There are no pending requests to review." /></div>
        : visible.map((item) => (
          <div className="card pad" key={`${item.kind}-${item.id}`}
               style={{ display: 'flex', flexWrap: 'wrap', gap: 14, justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ minWidth: 260 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                <span className={`badge ${KIND_TONE[item.kind]}`}>{KIND_LABEL[item.kind]}</span>
                <strong>{item.user.full_name}</strong>
                <span style={{ color: 'var(--ink-3)', fontSize: 12 }}>{item.user.department || ''}</span>
              </div>
              <div style={{ fontSize: 13.5 }}>
                {item.kind === 'leave' && <>{titleCase(item.leave_type)} · {fmtDate(item.start_date)} → {fmtDate(item.end_date)} · <strong>{item.days} day{item.days === 1 ? '' : 's'}</strong></>}
                {item.kind === 'wfh' && <>WFH on <strong>{fmtDate(item.date)}</strong></>}
                {item.kind === 'regularization' && <>{fmtDate(item.date)} · In {fmtTime(item.requested_check_in)} / Out {fmtTime(item.requested_check_out)}</>}
              </div>
              <div style={{ color: 'var(--ink-2)', fontSize: 12.5, marginTop: 2 }}>“{item.reason}”</div>
              <div style={{ color: 'var(--ink-3)', fontSize: 11.5, marginTop: 2 }}>Requested {fmtDateTime(item.created_at)}</div>
            </div>
            <div className="toolbar">
              <button className="btn success sm" onClick={() => setModal({ item, decision: 'approve' })}>Approve</button>
              <button className="btn danger sm" onClick={() => setModal({ item, decision: 'reject' })}>Reject</button>
            </div>
          </div>
        ))}

      {modal && <DecisionModal item={modal.item} decision={modal.decision}
                               onClose={() => setModal(null)}
                               onDone={() => { setModal(null); load() }} />}
    </div>
  )
}
