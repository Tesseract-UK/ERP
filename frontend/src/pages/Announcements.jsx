// HR/Admin: publish company announcements (notifies all active employees).
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  ConfirmDialog, EmptyState, Field, Spinner, fmtDateTime, useToast,
} from '../components/ui'
import { Megaphone } from '../components/icons'

export default function Announcements() {
  const toast = useToast()
  const [rows, setRows] = useState(null)
  const [form, setForm] = useState({ title: '', body: '' })
  const [busy, setBusy] = useState(false)
  const [toDelete, setToDelete] = useState(null)

  const load = useCallback(() => {
    api.get('/admin/announcements').then(setRows).catch((e) => toast(e.message, 'error'))
  }, [toast])
  useEffect(load, [load])

  const publish = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.post('/admin/announcements', form)
      toast('Announcement published — all employees notified', 'success')
      setForm({ title: '', body: '' })
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    setBusy(true)
    try {
      await api.del(`/admin/announcements/${toDelete.id}`)
      toast('Announcement deleted', 'success')
      setToDelete(null)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid cols-2" style={{ alignItems: 'start' }}>
      <div className="card">
        <div className="card-head"><h3>New Announcement</h3></div>
        <form className="card-body" onSubmit={publish}>
          <Field label="Title" required>
            <input className="input" required maxLength={200} value={form.title}
                   onChange={(e) => setForm({ ...form, title: e.target.value })} />
          </Field>
          <Field label="Message" required help="Every active employee receives an in-app notification.">
            <textarea className="input" required maxLength={5000} rows={5} value={form.body}
                      onChange={(e) => setForm({ ...form, body: e.target.value })} />
          </Field>
          <button className="btn" disabled={busy}>{busy ? 'Publishing…' : 'Publish Announcement'}</button>
        </form>
      </div>

      <div className="card">
        <div className="card-head"><h3>Published</h3></div>
        {rows === null ? <Spinner /> : rows.length === 0
          ? <EmptyState icon={Megaphone} title="No announcements yet" />
          : (
            <div className="card-body">
              {rows.map((a) => (
                <div key={a.id} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <strong>{a.title}</strong>
                    <button className="btn ghost sm" style={{ color: 'var(--danger)' }}
                            onClick={() => setToDelete(a)}>Delete</button>
                  </div>
                  <div style={{ color: 'var(--ink-2)', fontSize: 13 }}>{a.body}</div>
                  <div className="help-text">{a.created_by} · {fmtDateTime(a.created_at)}</div>
                </div>
              ))}
            </div>
          )}
      </div>

      {toDelete && <ConfirmDialog danger busy={busy} title="Delete announcement"
        message={`Delete "${toDelete.title}"? Employees keep any notifications already sent.`}
        confirmLabel="Delete" onConfirm={remove} onClose={() => setToDelete(null)} />}
    </div>
  )
}
