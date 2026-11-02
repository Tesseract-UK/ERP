// Manager/HR approvals inbox for leave, WFH and regularization requests.
import { useCallback, useEffect, useState } from 'react'
import { api, API_BASE } from '../api'
import { useAuth } from '../AuthContext'
import {
  EmptyState, Field, Modal, Spinner, StatusBadge, fmtDate, fmtDateTime, fmtTime, titleCase, useToast,
} from '../components/ui'
import { CheckCircle2 } from '../components/icons'

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
      {item.document_path && <p style={{ marginBottom: 14 }}>
        <a href={`${API_BASE}/files/${item.document_path.split(/[\\/]/).map(encodeURIComponent).join('/')}`}
           target="_blank" rel="noreferrer">Open supporting document</a>
      </p>}
      {item.manager_decided_at && <div className="card pad" style={{ marginBottom: 14 }}>
        <strong>Manager review: Approved</strong>
        <div className="help-text">{item.manager_approver_name || 'Assigned manager'} · {fmtDateTime(item.manager_decided_at)}</div>
        {item.manager_comment && <p style={{ marginTop: 8 }}>“{item.manager_comment}”</p>}
      </div>}
      <p className="help-text">Submitted {fmtDateTime(item.created_at)} · Current stage: {item.approval_stage === 'pending_hr' ? 'HR review' : 'Manager review'}</p>
      <Field label="Comment (optional)" help="Stored with the request for future reference">
        <textarea className="input" value={comment} onChange={(e) => setComment(e.target.value)}
                  placeholder="Add a note for the employee…" />
      </Field>
    </Modal>
  )
}

export default function Approvals() {
  const toast = useToast()
  const { user } = useAuth()
  const [items, setItems] = useState(null)
  const [filter, setFilter] = useState('all')
  const [view, setView] = useState('pending')
  const [history, setHistory] = useState(null)
  const [teamMembers, setTeamMembers] = useState([])
  const [historyFilter, setHistoryFilter] = useState({ employee: '', kind: 'all', status: 'all' })
  const [selectedHistoryItem, setSelectedHistoryItem] = useState(null)
  const [modal, setModal] = useState(null) // { item, decision }

  const load = useCallback(() => {
    api.get('/approvals/pending').then(setItems).catch((e) => toast(e.message, 'error'))
  }, [toast])
  const loadHistory = useCallback(() => {
    api.get('/approvals/team-history').then(setHistory).catch((e) => toast(e.message, 'error'))
  }, [toast])
  useEffect(load, [load])
  useEffect(() => {
    if (user.role === 'manager') api.get('/team/members').then(setTeamMembers).catch((e) => toast(e.message, 'error'))
  }, [user.role, toast])
  useEffect(() => { if (view === 'history' && history === null) loadHistory() }, [view, history, loadHistory])

  if (items === null) return <Spinner />
  const visible = filter === 'all' ? items : items.filter((i) => i.kind === filter)
  const historicalItems = history || []
  const filteredHistory = historicalItems.filter((item) =>
    (historyFilter.employee === '' || String(item.user?.id) === historyFilter.employee)
    && (historyFilter.kind === 'all' || item.kind === historyFilter.kind)
    && (historyFilter.status === 'all' || item.status === historyFilter.status))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h2>{view === 'pending' ? 'Pending Approvals' : 'Team Request History'}</h2>
          <div className="sub">{view === 'pending'
            ? `${items.length} request${items.length === 1 ? '' : 's'} awaiting your review`
            : 'Requests submitted by your direct reports, including requests already reviewed by you.'}</div></div>
        <div className="toolbar">
          <button className={`btn sm ${view === 'pending' ? '' : 'secondary'}`} onClick={() => setView('pending')}>Pending</button>
          {user.role === 'manager' && <button className={`btn sm ${view === 'history' ? '' : 'secondary'}`} onClick={() => setView('history')}>Team history</button>}
        </div>
      </div>

      {view === 'pending' && <div className="toolbar">
          <select className="input" style={{ width: 'auto' }} value={filter}
                  onChange={(e) => setFilter(e.target.value)}>
            <option value="all">All types</option>
            <option value="leave">Leave</option>
            <option value="wfh">Work From Home</option>
            <option value="regularization">Regularization</option>
          </select>
      </div>}

      {view === 'pending' && (visible.length === 0
        ? <div className="card"><EmptyState icon={CheckCircle2} title="All caught up!"
            hint="There are no pending requests to review." /></div>
        : visible.map((item) => (
          <div className="card pad" key={`${item.kind}-${item.id}`}
               style={{ display: 'flex', flexWrap: 'wrap', gap: 14, justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ minWidth: 260 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4 }}>
                <span className={`badge ${KIND_TONE[item.kind]}`}>{KIND_LABEL[item.kind]}</span>
                <span className="badge warn">{user.role === 'admin' ? 'Admin can decide' : item.approval_stage === 'pending_hr' ? 'HR review' : 'Manager review'}</span>
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
              {user.role === 'hr' && item.approval_stage === 'pending_hr' && <div className="help-text" style={{ marginTop: 4 }}>
                Manager approved{item.manager_approver_name ? ` · ${item.manager_approver_name}` : ''}
                {item.manager_decided_at ? ` · ${fmtDateTime(item.manager_decided_at)}` : ''}
                {item.manager_comment ? ` · “${item.manager_comment}”` : ''}
              </div>}
            </div>
            <div className="toolbar">
              <button className="btn success sm" onClick={() => setModal({ item, decision: 'approve' })}>Approve</button>
              <button className="btn danger sm" onClick={() => setModal({ item, decision: 'reject' })}>Reject</button>
            </div>
          </div>
        )))}

      {view === 'history' && <>
        <div className="card pad toolbar">
          <select className="input" style={{ width: 'auto', minWidth: 190 }} value={historyFilter.employee}
            onChange={(e) => setHistoryFilter((current) => ({ ...current, employee: e.target.value }))}>
            <option value="">All team members ({teamMembers.length})</option>
            {teamMembers.map((member) => <option key={member.id} value={member.id}>
              {member.full_name} · {member.employee_code}
            </option>)}
          </select>
          <select className="input" style={{ width: 'auto' }} value={historyFilter.kind}
            onChange={(e) => setHistoryFilter((current) => ({ ...current, kind: e.target.value }))}>
            <option value="all">All request types</option>
            {Object.entries(KIND_LABEL).map(([kind, label]) => <option key={kind} value={kind}>{label}</option>)}
          </select>
          <select className="input" style={{ width: 'auto' }} value={historyFilter.status}
            onChange={(e) => setHistoryFilter((current) => ({ ...current, status: e.target.value }))}>
            <option value="all">All statuses</option>
            {['pending', 'approved', 'rejected'].map((status) => <option key={status} value={status}>{titleCase(status)}</option>)}
          </select>
          <span className="help-text">{filteredHistory.length} request{filteredHistory.length === 1 ? '' : 's'}</span>
          <button className="btn secondary sm" onClick={loadHistory}>Refresh</button>
        </div>
        {history === null
          ? <Spinner />
          : filteredHistory.length === 0
            ? <div className="card"><EmptyState icon={CheckCircle2} title={historicalItems.length ? 'No requests match these filters' : 'No team requests yet'}
                hint={historicalItems.length ? 'Change a filter to see other team requests.' : 'Requests from your direct reports will appear here.'} /></div>
            : filteredHistory.map((item) => (
            <div className="card pad" key={`history-${item.kind}-${item.id}`}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                <span className={`badge ${KIND_TONE[item.kind]}`}>{KIND_LABEL[item.kind]}</span>
                <StatusBadge status={item.status} />
                <strong>{item.user?.full_name || 'Unknown employee'}</strong>
                <span className="help-text">{item.user?.employee_code || 'No employee code'}</span>
                {item.user?.department && <span className="help-text">{item.user.department}</span>}
                {item.user?.designation && <span className="help-text">{item.user.designation}</span>}
                <span className="badge neutral">{titleCase(item.approval_stage || 'pending')}</span>
              </div>
              <div style={{ marginTop: 8, fontSize: 13 }}>
                {item.kind === 'leave' && <>{titleCase(item.leave_type)} · {fmtDate(item.start_date)} → {fmtDate(item.end_date)} · {item.days} day(s)</>}
                {item.kind === 'wfh' && <>WFH · {fmtDate(item.date)}</>}
                {item.kind === 'regularization' && <>{fmtDate(item.date)} · In {fmtTime(item.requested_check_in)} / Out {fmtTime(item.requested_check_out)}</>}
              </div>
              <div className="help-text" style={{ marginTop: 4 }}>“{item.reason}” · Submitted {fmtDateTime(item.created_at)}</div>
              {item.manager_decided_at && <div className="help-text" style={{ marginTop: 4 }}>
                Manager reviewed{item.manager_approver_name ? ` by ${item.manager_approver_name}` : ''} · {fmtDateTime(item.manager_decided_at)}
                {item.manager_comment ? ` · “${item.manager_comment}”` : ''}
              </div>}
              {item.hr_decided_at && <div className="help-text" style={{ marginTop: 4 }}>
                HR reviewed · {fmtDateTime(item.hr_decided_at)}{item.hr_comment ? ` · “${item.hr_comment}”` : ''}
              </div>}
              {item.approver_comment && <div className="help-text" style={{ marginTop: 4 }}>Final decision note: “{item.approver_comment}”</div>}
              <div style={{ marginTop: 10 }}><button className="btn secondary sm" onClick={() => setSelectedHistoryItem(item)}>View full request</button></div>
            </div>
          ))}
      </>}

      {modal && <DecisionModal item={modal.item} decision={modal.decision}
                               onClose={() => setModal(null)}
                               onDone={() => { setModal(null); load() }} />}
      {selectedHistoryItem && <Modal title={`${KIND_LABEL[selectedHistoryItem.kind]} request details`} onClose={() => setSelectedHistoryItem(null)}>
        <p><strong>Team member:</strong> {selectedHistoryItem.user?.full_name} · {selectedHistoryItem.user?.employee_code}</p>
        {selectedHistoryItem.user?.department && <p><strong>Department:</strong> {selectedHistoryItem.user.department}</p>}
        {selectedHistoryItem.user?.designation && <p><strong>Role:</strong> {selectedHistoryItem.user.designation}</p>}
        {selectedHistoryItem.kind === 'leave' && <p><strong>Leave:</strong> {titleCase(selectedHistoryItem.leave_type)} · {fmtDate(selectedHistoryItem.start_date)} → {fmtDate(selectedHistoryItem.end_date)} · {selectedHistoryItem.days} day(s)</p>}
        {selectedHistoryItem.kind === 'wfh' && <p><strong>Work from home:</strong> {fmtDate(selectedHistoryItem.date)}</p>}
        {selectedHistoryItem.kind === 'regularization' && <p><strong>Attendance correction:</strong> {fmtDate(selectedHistoryItem.date)} · In {fmtTime(selectedHistoryItem.requested_check_in)} / Out {fmtTime(selectedHistoryItem.requested_check_out)}</p>}
        <p><strong>Status:</strong> {titleCase(selectedHistoryItem.status)} · {titleCase(selectedHistoryItem.approval_stage || 'complete')}</p>
        <p><strong>Reason:</strong> {selectedHistoryItem.reason}</p>
        <p><strong>Submitted:</strong> {fmtDateTime(selectedHistoryItem.created_at)}</p>
        {selectedHistoryItem.manager_decided_at && <p><strong>Manager review:</strong> {selectedHistoryItem.manager_approver_name || 'Manager'} · {fmtDateTime(selectedHistoryItem.manager_decided_at)}{selectedHistoryItem.manager_comment ? ` · ${selectedHistoryItem.manager_comment}` : ''}</p>}
        {selectedHistoryItem.hr_decided_at && <p><strong>HR review:</strong> {fmtDateTime(selectedHistoryItem.hr_decided_at)}{selectedHistoryItem.hr_comment ? ` · ${selectedHistoryItem.hr_comment}` : ''}</p>}
        {selectedHistoryItem.approver_comment && <p><strong>Final decision note:</strong> {selectedHistoryItem.approver_comment}</p>}
        {selectedHistoryItem.document_path && <p style={{ marginTop: 12 }}><a href={`${API_BASE}/files/${selectedHistoryItem.document_path.split(/[\\/]/).map(encodeURIComponent).join('/')}`} target="_blank" rel="noreferrer">Open supporting document</a></p>}
      </Modal>}
    </div>
  )
}
