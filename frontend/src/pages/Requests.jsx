import { useCallback, useEffect, useState } from 'react'
import { api, API_BASE } from '../api'
import { EmptyState, Field, Pagination, Spinner, fmtDateTime, titleCase, useToast } from '../components/ui'
import { MessageSquare } from '../components/icons'
import { useAuth } from '../AuthContext'

const ACTIVE = new Set(['open', 'in_progress'])

export default function Requests() {
  const toast = useToast()
  const { user } = useAuth()
  const isAdmin = user.role === 'admin'
  const [rows, setRows] = useState(null)
  const [pageData, setPageData] = useState(null)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [contacts, setContacts] = useState([])
  const [selected, setSelected] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({ title: '', category: 'IT support', otherCategory: '', priority: 'normal', description: '', recipient_ids: [], attachment: null })
  const [comment, setComment] = useState('')
  const [mentions, setMentions] = useState([])

  const load = useCallback(async () => {
    try {
      if (isAdmin) {
        const params = new URLSearchParams({ page, page_size: 25 })
        if (statusFilter) params.set('status', statusFilter)
        const result = await api.get(`/requests?${params}`)
        setRows(result.items)
        setPageData(result)
      } else {
        setRows(await api.get('/requests'))
        setPageData(null)
      }
    } catch (e) { toast(e.message, 'error') }
  }, [isAdmin, page, statusFilter, toast])
  useEffect(() => {
    load()
    api.get('/requests/recipients').then(setContacts).catch((e) => toast(e.message, 'error'))
  }, [load, toast])

  const openRequest = async (id) => {
    try { setSelected(await api.get(`/requests/${id}`)); setComment(''); setMentions([]) }
    catch (e) { toast(e.message, 'error') }
  }
  const submit = async (e) => {
    e.preventDefault()
    const category = form.category === 'Other' ? form.otherCategory.trim() : form.category
    if (!category) { toast('Enter the request category', 'error'); return }
    const data = new FormData()
    Object.entries({ ...form, category }).forEach(([key, value]) => {
      if (key === 'otherCategory') return
      if (key === 'attachment') { if (value) data.append(key, value) }
      else data.append(key, key === 'recipient_ids' ? JSON.stringify(value) : value)
    })
    setBusy(true)
    try {
      const item = await api.postForm('/requests', data)
      toast('Request sent', 'success'); setCreateOpen(false)
      setForm({ title: '', category: 'IT support', otherCategory: '', priority: 'normal', description: '', recipient_ids: [], attachment: null })
      await load(); setSelected(item)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }
  const act = async (path, body) => {
    setBusy(true)
    try { await api.post(path, body); await load(); if (selected) await openRequest(selected.id); toast('Updated', 'success') }
    catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  if (rows === null) return <Spinner />
  return <div style={{ display: 'grid', gridTemplateColumns: selected ? 'minmax(260px, .8fr) minmax(320px, 1.2fr)' : '1fr', gap: 16, alignItems: 'start' }}>
    <section className="card">
      <div className="card-head" style={{ justifyContent: 'space-between' }}><div><h3>{isAdmin ? 'All Employee Requests' : 'My Requests'}</h3><div className="sub">{isAdmin ? `${pageData?.total ?? 0} requests across the organization. Open a request to review or manage it.` : 'Private conversations shared with the people you mention.'}</div></div><button className="btn sm" onClick={() => setCreateOpen(true)}>New Request</button></div>
      {isAdmin && <div className="card-body toolbar" style={{ paddingBottom: 0 }}>
        <select className="input" style={{ maxWidth: 210 }} value={statusFilter}
          onChange={(event) => { setStatusFilter(event.target.value); setPage(1) }}>
          <option value="">All statuses</option>
          {['open', 'in_progress', 'resolved', 'rejected', 'withdrawn'].map((status) =>
            <option key={status} value={status}>{titleCase(status)}</option>)}
        </select>
      </div>}
      {rows.length === 0 ? <EmptyState icon={MessageSquare} title={isAdmin ? 'No employee requests found' : 'No requests yet'} hint={isAdmin ? 'Try a different status filter.' : 'Create a request and choose who should receive it.'} /> : <div className="card-body" style={{ paddingTop: 0 }}>
        {rows.map((r) => <button key={r.id} className="card" onClick={() => openRequest(r.id)} style={{ width: '100%', textAlign: 'left', padding: 14, marginTop: 10, cursor: 'pointer' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}><strong>{r.title}</strong><span className="badge neutral">{titleCase(r.status)}</span></div>
          <div className="help-text">{r.requester_name} · {r.category} · {titleCase(r.priority)} · {fmtDateTime(r.updated_at)}</div>
        </button>)}
      </div>}
      {isAdmin && pageData && pageData.total > pageData.page_size &&
        <div className="card-body" style={{ paddingTop: 0 }}>
          <Pagination page={pageData.page} pageSize={pageData.page_size} total={pageData.total} onPage={setPage} />
        </div>}
    </section>

    {selected && <section className="card"><div className="card-head" style={{ justifyContent: 'space-between' }}><div><h3>{selected.title}</h3><div className="sub">{selected.requester_name} · {selected.category} · {titleCase(selected.status)}</div></div><button className="btn ghost sm" onClick={() => setSelected(null)}>Close</button></div>
      <div className="card-body"><p style={{ whiteSpace: 'pre-wrap' }}>{selected.description}</p>
        {selected.attachment_path && <p><a href={`${API_BASE}/files/${selected.attachment_path.split(/[\\/]/).map(encodeURIComponent).join('/')}`} target="_blank" rel="noreferrer">Open attachment</a></p>}
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10, marginTop: 10 }}><strong>Conversation</strong>
          {(selected.messages || []).map((m) => <div key={m.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}><strong>{m.user_name}</strong> <span className="help-text">· {fmtDateTime(m.created_at)} · {titleCase(m.type)}</span><div style={{ whiteSpace: 'pre-wrap' }}>{m.body}</div></div>)}
        </div>
        {selected.can_reply && <form onSubmit={(e) => { e.preventDefault(); act(`/requests/${selected.id}/comments`, { body: comment, recipient_ids: mentions }); setComment('') }} style={{ marginTop: 14 }}>
          <Field label="Reply" required><textarea className="input" required value={comment} onChange={(e) => setComment(e.target.value)} /></Field>
          <Field label="Mention people" required help="Choose at least one recipient for this reply."><select className="input" multiple value={mentions.map(String)} onChange={(e) => setMentions([...e.target.selectedOptions].map((o) => Number(o.value)))}>{contacts.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.role})</option>)}</select></Field>
          <button className="btn sm" disabled={busy || mentions.length === 0}>Send Reply</button>
        </form>}
        <div className="toolbar" style={{ marginTop: 14 }}>
          {selected.can_withdraw && ACTIVE.has(selected.status) && <button className="btn danger sm" disabled={busy} onClick={() => act(`/requests/${selected.id}/withdraw`)}>Withdraw</button>}
          {selected.can_update_status && ACTIVE.has(selected.status) && <><button className="btn secondary sm" disabled={busy} onClick={() => act(`/requests/${selected.id}/status`, { status: 'in_progress' })}>In Progress</button><button className="btn success sm" disabled={busy} onClick={() => act(`/requests/${selected.id}/status`, { status: 'resolved' })}>Resolve</button><button className="btn danger sm" disabled={busy} onClick={() => act(`/requests/${selected.id}/status`, { status: 'rejected' })}>Reject</button></>}
        </div>
      </div>
    </section>}

    {createOpen && <div className="modal-overlay"><div className="modal wide" role="dialog" aria-modal="true"><div className="modal-head"><h3>New Employee Request</h3><button className="close-x" onClick={() => setCreateOpen(false)}>×</button></div><form onSubmit={submit}><div className="modal-body">
      <Field label="Title" required><input className="input" required maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
      <div className="grid cols-2"><Field label="Category" required><select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value, otherCategory: '' })}>{['IT support', 'HR', 'Payroll', 'Facilities', 'Other'].map((x) => <option key={x}>{x}</option>)}</select></Field><Field label="Priority"><select className="input" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>{['low', 'normal', 'high'].map((x) => <option key={x} value={x}>{titleCase(x)}</option>)}</select></Field></div>
      {form.category === 'Other' && <Field label="Specify category" required><input className="input" required maxLength={80} value={form.otherCategory} onChange={(e) => setForm({ ...form, otherCategory: e.target.value })} placeholder="Enter another category" /></Field>}
      <Field label="Description" required><textarea className="input" required minLength={3} maxLength={10000} rows={5} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
      <Field label="Mention people" required help="Choose one to three people. Their role and access are checked again by the server."><select className="input" required multiple value={form.recipient_ids.map(String)} onChange={(e) => setForm({ ...form, recipient_ids: [...e.target.selectedOptions].map((o) => Number(o.value)) })}>{contacts.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.role})</option>)}</select></Field>
      <Field label="Attachment (optional)"><input className="input" type="file" onChange={(e) => setForm({ ...form, attachment: e.target.files?.[0] || null })} /></Field>
    </div><div className="modal-foot"><button type="button" className="btn secondary" onClick={() => setCreateOpen(false)}>Cancel</button><button className="btn" disabled={busy || form.recipient_ids.length < 1 || form.recipient_ids.length > 3}>{busy ? 'Sending…' : 'Send Request'}</button></div></form></div></div>}
  </div>
}
