// Request conversations: the thread modal (read, reply with @-tags, decide)
// and the list used by the Conversations page and the notifications panel.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import MentionTextarea from './MentionTextarea'
import { KindBadge, searchPeople } from './RequestForms'
import {
  ConfirmDialog, EmptyState, Field, Modal, Spinner, StatusBadge,
  fmtDate, fmtDateTime, fmtTime, initials, titleCase, useToast,
} from './ui'
import { MessageSquare } from './icons'

export function requestSummary(r) {
  if (r.kind === 'leave') return `${titleCase(r.leave_type)} · ${fmtDate(r.start_date)} → ${fmtDate(r.end_date)} · ${r.days} day${r.days === 1 ? '' : 's'}`
  if (r.kind === 'wfh') return `Work from home on ${fmtDate(r.date)}`
  return `${fmtDate(r.date)} · In ${fmtTime(r.requested_check_in)} / Out ${fmtTime(r.requested_check_out)}`
}

/** Approve, or reject with a second "are you sure" step. */
export function DecisionFlow({ request, decision, onClose, onDone }) {
  const toast = useToast()
  const [comment, setComment] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const name = request.user?.full_name || 'this employee'

  const submit = async () => {
    setBusy(true)
    try {
      await api.post(`/approvals/${request.kind}/${request.id}/${decision}`, { comment: comment.trim() || null })
      toast(`Request ${decision === 'approve' ? 'approved' : 'rejected'}`, 'success')
      onDone()
    } catch (err) {
      toast(err.message, 'error')
      setConfirming(false)
    } finally {
      setBusy(false)
    }
  }

  if (confirming) {
    return <ConfirmDialog danger busy={busy} title="Confirm rejection"
      message={`Are you sure you want to reject ${name}'s request (${requestSummary(request)})? They will be notified and this cannot be undone.`}
      confirmLabel="Yes, reject it" onConfirm={submit} onClose={() => setConfirming(false)} />
  }
  const isReject = decision === 'reject'
  return (
    <Modal title={`${isReject ? 'Reject' : 'Approve'} request`} onClose={onClose} footer={
      <>
        <button className="btn secondary" onClick={onClose} disabled={busy}>Cancel</button>
        <button className={`btn ${isReject ? 'danger' : 'success'}`} disabled={busy}
          onClick={() => (isReject ? setConfirming(true) : submit())}>
          {busy ? 'Working…' : isReject ? 'Reject…' : 'Approve'}
        </button>
      </>
    }>
      <p style={{ marginBottom: 12 }}><strong>{name}</strong> — {requestSummary(request)}</p>
      <p style={{ color: 'var(--ink-2)', marginBottom: 14 }}>Reason: “{request.reason}”</p>
      <Field label={isReject ? 'Reason for rejection (recommended)' : 'Comment (optional)'}
             help="Posted in the request's conversation">
        <textarea className="input" value={comment} onChange={(e) => setComment(e.target.value)}
                  placeholder="Add a note for the employee…" />
      </Field>
    </Modal>
  )
}

export function ConversationModal({ kind, id, onClose, onChanged }) {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [text, setText] = useState('')
  const [mentionedIds, setMentionedIds] = useState([])
  const [busy, setBusy] = useState(false)
  const [decision, setDecision] = useState(null)
  const search = useCallback(searchPeople, [])

  const load = useCallback(() => {
    api.get(`/conversations/${kind}/${id}`).then(setData).catch((e) => setError(e.message))
  }, [kind, id])
  useEffect(load, [load])

  const send = async (e) => {
    e.preventDefault()
    if (!text.trim()) return
    setBusy(true)
    try {
      setData(await api.post(`/conversations/${kind}/${id}/comments`, { body: text, mentioned_user_ids: mentionedIds }))
      setText('')
      setMentionedIds([])
      onChanged?.()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (decision && data) {
    return <DecisionFlow request={data.request} decision={decision} onClose={() => setDecision(null)}
      onDone={() => { setDecision(null); load(); onChanged?.() }} />
  }

  const r = data?.request
  return (
    <Modal wide title={data ? data.heading : 'Conversation'} onClose={onClose}>
      {error && <p className="error-text">{error}</p>}
      {!data && !error && <Spinner />}
      {data && <>
        <div className="convo-head">
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <KindBadge kind={kind} /><StatusBadge status={r.status} />
            <span className="help-text">{requestSummary(r)}</span>
          </div>
          <div className="help-text" style={{ marginTop: 6 }}>
            Requested by <strong>{data.requester?.full_name}</strong>
            {data.manager && <> · Manager <strong>{data.manager.full_name}</strong></>}
            {data.participants.length > 0 && <> · Tagged {data.participants.map((p) => p.full_name).join(', ')}</>}
          </div>
          {data.can_decide && (
            <div className="toolbar" style={{ marginTop: 10 }}>
              <button className="btn success sm" onClick={() => setDecision('approve')}>Approve</button>
              <button className="btn danger sm" onClick={() => setDecision('reject')}>Reject</button>
            </div>
          )}
        </div>
        <div className="convo-thread">
          <Message user={data.requester} at={r.created_at} body={r.reason} note="opened the request" />
          {data.comments.map((c) => (
            <Message key={c.id} user={c.user} at={c.created_at} body={c.body}
                     decision={c.message_type === 'decision'} />
          ))}
        </div>
        <form onSubmit={send} className="convo-reply">
          <MentionTextarea className="input" rows={2} value={text} onChange={setText}
            searchUsers={search} mentionedIds={mentionedIds} onMentionsChange={setMentionedIds}
            placeholder="Write a reply… type @ to tag someone into this conversation" />
          <button className="btn" disabled={busy || !text.trim()}>{busy ? 'Sending…' : 'Send'}</button>
        </form>
      </>}
    </Modal>
  )
}

function Message({ user, at, body, decision, note }) {
  return (
    <div className={`convo-msg${decision ? ' decision' : ''}`}>
      <div className="avatar sm">{initials(user?.full_name)}</div>
      <div style={{ minWidth: 0 }}>
        <div className="help-text"><strong style={{ color: 'var(--ink)' }}>{user?.full_name || 'Unknown'}</strong>
          {note ? ` ${note}` : ''} · {fmtDateTime(at)}</div>
        <div style={{ whiteSpace: 'pre-wrap', marginTop: 2 }}>{body}</div>
      </div>
    </div>
  )
}

/** Conversation list; `scope="all"` is the Admin view of every conversation. */
export function ConversationList({ scope = 'mine', onOpen, compact }) {
  const toast = useToast()
  const [items, setItems] = useState(null)
  const [filter, setFilter] = useState('')

  const load = useCallback(() => {
    api.get(`/conversations?scope=${scope}`).then(setItems).catch((e) => toast(e.message, 'error'))
  }, [scope, toast])
  useEffect(load, [load])

  if (items === null) return <Spinner />
  const term = filter.trim().toLowerCase()
  const visible = term ? items.filter((c) => `${c.heading} ${c.last_message}`.toLowerCase().includes(term)) : items
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {!compact && <input className="input" placeholder="Search conversations…" value={filter}
                          onChange={(e) => setFilter(e.target.value)} />}
      {visible.length === 0 && <EmptyState icon={MessageSquare} title="No conversations yet"
        hint="Requests you raise, review or are tagged in appear here." />}
      {visible.map((c) => (
        <button type="button" key={`${c.kind}-${c.id}`} className="notif-item"
                onClick={() => onOpen(c.kind, c.id, load)}>
          <div className="t" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <KindBadge kind={c.kind} /><StatusBadge status={c.status} />
            {c.tagged && <span className="badge info">You are tagged</span>}
            <span>{c.heading}</span>
          </div>
          <div className="b">{c.last_message}</div>
          <div className="time">{c.message_count} message{c.message_count === 1 ? '' : 's'} · {fmtDateTime(c.last_activity)}</div>
        </button>
      ))}
    </div>
  )
}
