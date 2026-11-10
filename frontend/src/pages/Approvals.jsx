// Approvals inbox for leave, WFH and regularization requests. A manager sees
// their direct reports; an Admin sees everything and can override.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import { EmptyState, Spinner, StatusBadge, fmtDateTime, titleCase, useToast } from '../components/ui'
import { CheckCircle2 } from '../components/icons'
import { KIND_META, KindBadge } from '../components/RequestForms'
import { ConversationModal, DecisionFlow, requestSummary } from '../components/Conversation'

export default function Approvals() {
  const toast = useToast()
  const { user } = useAuth()
  const isAdmin = user.role === 'admin'
  const [items, setItems] = useState(null)
  const [filter, setFilter] = useState('all')
  const [view, setView] = useState('pending')
  const [history, setHistory] = useState(null)
  const [historyFilter, setHistoryFilter] = useState({ employee: '', kind: 'all', status: 'all' })
  const [decision, setDecision] = useState(null) // { item, decision }
  const [openItem, setOpenItem] = useState(null)

  const load = useCallback(() => {
    api.get('/approvals/pending').then(setItems).catch((e) => toast(e.message, 'error'))
  }, [toast])
  const loadHistory = useCallback(() => {
    api.get('/approvals/team-history').then(setHistory).catch((e) => toast(e.message, 'error'))
  }, [toast])
  useEffect(load, [load])
  useEffect(() => { if (view === 'history' && history === null) loadHistory() }, [view, history, loadHistory])
  const refresh = () => { load(); if (history !== null) loadHistory() }

  if (items === null) return <Spinner />
  const visible = filter === 'all' ? items : items.filter((i) => i.kind === filter)
  const people = [...new Map((history || []).map((i) => [i.user?.id, i.user])).values()].filter(Boolean)
  const filteredHistory = (history || []).filter((item) =>
    (historyFilter.employee === '' || String(item.user?.id) === historyFilter.employee)
    && (historyFilter.kind === 'all' || item.kind === historyFilter.kind)
    && (historyFilter.status === 'all' || item.status === historyFilter.status))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h2>{view === 'pending' ? 'Pending Approvals' : isAdmin ? 'All Requests' : 'Team Request History'}</h2>
          <div className="sub">{view === 'pending'
            ? `${items.length} request${items.length === 1 ? '' : 's'} awaiting ${isAdmin ? 'a decision (Admin override available)' : 'your review'}`
            : isAdmin ? 'Every leave, WFH and regularization request.' : 'Requests submitted by your direct reports.'}</div></div>
        <div className="toolbar">
          <button className={`btn sm ${view === 'pending' ? '' : 'secondary'}`} onClick={() => setView('pending')}>Pending</button>
          <button className={`btn sm ${view === 'history' ? '' : 'secondary'}`} onClick={() => setView('history')}>History</button>
        </div>
      </div>

      {view === 'pending' && <div className="toolbar">
        <select className="input" style={{ width: 'auto' }} value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="all">All types</option>
          {Object.entries(KIND_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
        </select>
      </div>}

      {view === 'pending' && (visible.length === 0
        ? <div className="card"><EmptyState icon={CheckCircle2} title="All caught up!"
            hint="There are no pending requests to review." /></div>
        : visible.map((item) => (
          <div className={`card pad row-${item.kind}`} key={`${item.kind}-${item.id}`}
               style={{ display: 'flex', flexWrap: 'wrap', gap: 14, justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ minWidth: 260, flex: 1 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4, flexWrap: 'wrap' }}>
                <KindBadge kind={item.kind} />
                {isAdmin && !item.is_direct_report && <span className="badge neutral">Admin override</span>}
                <strong>{item.user.full_name}</strong>
                <span style={{ color: 'var(--ink-3)', fontSize: 12 }}>{item.user.department || ''}</span>
              </div>
              <div style={{ fontSize: 13.5 }}>{requestSummary(item)}</div>
              <div style={{ color: 'var(--ink-2)', fontSize: 12.5, marginTop: 2 }}>“{item.reason}”</div>
              <div style={{ color: 'var(--ink-3)', fontSize: 11.5, marginTop: 2 }}>Requested {fmtDateTime(item.created_at)}</div>
            </div>
            <div className="toolbar">
              <button className="btn ghost sm" onClick={() => setOpenItem(item)}>Conversation</button>
              <button className="btn success sm" onClick={() => setDecision({ item, decision: 'approve' })}>Approve</button>
              <button className="btn danger sm" onClick={() => setDecision({ item, decision: 'reject' })}>Reject</button>
            </div>
          </div>
        )))}

      {view === 'history' && <>
        <div className="card pad toolbar">
          <select className="input" style={{ width: 'auto', minWidth: 190 }} value={historyFilter.employee}
            onChange={(e) => setHistoryFilter((c) => ({ ...c, employee: e.target.value }))}>
            <option value="">Everyone ({people.length})</option>
            {people.map((p) => <option key={p.id} value={p.id}>{p.full_name} · {p.employee_code}</option>)}
          </select>
          <select className="input" style={{ width: 'auto' }} value={historyFilter.kind}
            onChange={(e) => setHistoryFilter((c) => ({ ...c, kind: e.target.value }))}>
            <option value="all">All request types</option>
            {Object.entries(KIND_META).map(([k, m]) => <option key={k} value={k}>{m.label}</option>)}
          </select>
          <select className="input" style={{ width: 'auto' }} value={historyFilter.status}
            onChange={(e) => setHistoryFilter((c) => ({ ...c, status: e.target.value }))}>
            <option value="all">All statuses</option>
            {['pending', 'approved', 'rejected', 'cancelled'].map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </select>
          <span className="help-text">{filteredHistory.length} request{filteredHistory.length === 1 ? '' : 's'}</span>
          <button className="btn secondary sm" onClick={loadHistory}>Refresh</button>
        </div>
        {history === null ? <Spinner /> : filteredHistory.length === 0
          ? <div className="card"><EmptyState icon={CheckCircle2} title="No requests match"
              hint="Change a filter to see other requests." /></div>
          : filteredHistory.map((item) => (
            <div className={`card pad row-${item.kind}`} key={`history-${item.kind}-${item.id}`}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                <KindBadge kind={item.kind} /><StatusBadge status={item.status} />
                <strong>{item.user?.full_name || 'Unknown employee'}</strong>
                <span className="help-text">{item.user?.employee_code}</span>
              </div>
              <div style={{ marginTop: 8, fontSize: 13 }}>{requestSummary(item)}</div>
              <div className="help-text" style={{ marginTop: 4 }}>“{item.reason}” · Submitted {fmtDateTime(item.created_at)}</div>
              {item.approver_name && <div className="help-text" style={{ marginTop: 4 }}>
                Decided by {item.approver_name}{item.decided_at ? ` · ${fmtDateTime(item.decided_at)}` : ''}
                {item.approver_comment ? ` · “${item.approver_comment}”` : ''}</div>}
              <div style={{ marginTop: 10 }}><button className="btn secondary sm" onClick={() => setOpenItem(item)}>Open conversation</button></div>
            </div>
          ))}
      </>}

      {decision && <DecisionFlow request={decision.item} decision={decision.decision}
        onClose={() => setDecision(null)} onDone={() => { setDecision(null); refresh() }} />}
      {openItem && <ConversationModal kind={openItem.kind} id={openItem.id}
        onClose={() => setOpenItem(null)} onChanged={refresh} />}
    </div>
  )
}
