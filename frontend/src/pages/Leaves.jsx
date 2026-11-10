// Leave & Work From Home: one screen to apply for either, see balances, and
// follow each request's conversation. Leave is red, WFH is orange.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import {
  ConfirmDialog, EmptyState, Modal, Spinner, StatusBadge, fmtDate, titleCase, useToast,
} from '../components/ui'
import { Plane } from '../components/icons'
import { ApplyRequestForm, KindBadge } from '../components/RequestForms'
import { ConversationModal } from '../components/Conversation'
import OnboardingNotice from '../components/OnboardingNotice'

export default function Leaves() {
  const toast = useToast()
  const { user } = useAuth()
  const [rows, setRows] = useState(null)
  const [balances, setBalances] = useState(null)
  const [showApply, setShowApply] = useState(false)
  const [filter, setFilter] = useState('all')
  const [cancelItem, setCancelItem] = useState(null)
  const [openItem, setOpenItem] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    Promise.all([api.get('/leaves'), api.get('/wfh')])
      .then(([leaves, wfh]) => setRows([...leaves, ...wfh]
        .sort((a, b) => b.created_at.localeCompare(a.created_at))))
      .catch((e) => toast(e.message, 'error'))
    api.get('/leaves/balance').then(setBalances).catch(() => {})
  }, [toast])
  useEffect(load, [load])

  const cancel = async () => {
    setBusy(true)
    try {
      await api.post(`/${cancelItem.kind === 'leave' ? 'leaves' : 'wfh'}/${cancelItem.id}/cancel`)
      toast('Request cancelled', 'success')
      setCancelItem(null)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const visible = (rows || []).filter((r) => filter === 'all' || r.kind === filter)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <OnboardingNotice />
      <div className="page-head" style={{ marginBottom: 0 }}>
        <div><h2>Leave &amp; Work From Home</h2>
          <div className="sub">Apply for leave or WFH and follow each request's conversation</div></div>
        <button className="btn" onClick={() => setShowApply(true)} disabled={!user.can_request}
                title={user.can_request ? undefined : "You haven't been assigned a manager yet"}>+ Apply</button>
      </div>

      {balances && (
        <div className="grid cols-4">
          {['casual', 'sick', 'earned'].map((t) => (
            <div className="card stat" key={t} style={{ boxShadow: 'inset 3px 0 0 var(--leave)' }}>
              <div className="label">{titleCase(t)} leave</div>
              <div className="value">{balances[t].remaining}</div>
              <div className="sub">used {balances[t].used} of {balances[t].allocated}</div>
            </div>
          ))}
          <div className="card stat" style={{ boxShadow: 'inset 3px 0 0 var(--wfh)' }}>
            <div className="label">Work from home</div>
            <div className="value">{balances.wfh.remaining}</div>
            <div className="sub">accrued {balances.wfh.allocated} · used {balances.wfh.used}</div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-head"><h3>My Requests</h3>
          <select className="input" style={{ width: 'auto' }} value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">Leave &amp; WFH</option>
            <option value="leave">Leave only</option>
            <option value="wfh">WFH only</option>
          </select>
        </div>
        {rows === null ? <Spinner /> : visible.length === 0
          ? <EmptyState icon={Plane} title="No requests yet" hint="Leave and WFH requests you submit will appear here." />
          : (
            <div className="table-wrap"><table className="table">
              <thead><tr><th>Type</th><th>Dates</th><th>Reason</th><th>Status</th><th>Reviewed By</th><th></th></tr></thead>
              <tbody>
                {visible.map((r) => (
                  <tr key={`${r.kind}-${r.id}`} className={`row-${r.kind}`}>
                    <td><KindBadge kind={r.kind} />
                      {r.kind === 'leave' && <div className="help-text">{titleCase(r.leave_type)} · {r.days} day{r.days === 1 ? '' : 's'}</div>}</td>
                    <td>{r.kind === 'leave' ? `${fmtDate(r.start_date)} → ${fmtDate(r.end_date)}` : fmtDate(r.date)}</td>
                    <td style={{ maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.reason}>{r.reason}</td>
                    <td><StatusBadge status={r.status} /></td>
                    <td>{r.approver_name || '—'}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button className="btn ghost sm" onClick={() => setOpenItem(r)}>Conversation</button>{' '}
                      {r.status === 'pending' && <button className="btn ghost sm" onClick={() => setCancelItem(r)}>Cancel</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
      </div>

      {showApply && (
        <Modal title="Apply for Leave or WFH" onClose={() => setShowApply(false)}>
          <ApplyRequestForm onCancel={() => setShowApply(false)}
                            onDone={() => { setShowApply(false); load() }} />
        </Modal>
      )}
      {openItem && <ConversationModal kind={openItem.kind} id={openItem.id}
                                      onClose={() => setOpenItem(null)} onChanged={load} />}
      {cancelItem && <ConfirmDialog title="Cancel request" danger busy={busy}
        message="Are you sure you want to cancel this pending request?"
        confirmLabel="Yes, cancel it" onConfirm={cancel} onClose={() => setCancelItem(null)} />}
    </div>
  )
}
