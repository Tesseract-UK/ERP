// Admin: departments, designations, locations, shifts and company settings.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import { Field, Spinner, useToast } from '../components/ui'

function ItemList({ title, items, nameKey, extra, onAdd, onToggle, addFields }) {
  const [form, setForm] = useState({})
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await onAdd(form)
      setForm({})
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="card">
      <div className="card-head"><h3>{title}</h3></div>
      <div className="card-body">
        <form onSubmit={submit} className="toolbar" style={{ marginBottom: 12 }}>
          {addFields.map((f) => (
            <input key={f.key} className="input" style={{ flex: 1, minWidth: 110 }}
                   placeholder={f.placeholder} required={f.required !== false}
                   type={f.type || 'text'} value={form[f.key] || ''}
                   onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />
          ))}
          <button className="btn sm" disabled={busy}>Add</button>
        </form>
        {items.map((i) => (
          <div key={i.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '7px 0', borderBottom: '1px solid var(--border)' }}>
            <span style={{ opacity: i.is_active ? 1 : 0.45 }}>
              {i[nameKey]}{extra ? <span className="help-text" style={{ display: 'inline', marginLeft: 8 }}>{extra(i)}</span> : null}
            </span>
            <button className="btn ghost sm" onClick={() => onToggle(i)}>
              {i.is_active ? 'Disable' : 'Enable'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Organization() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [settings, setSettings] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.get('/admin/org-data').then(setData).catch((e) => toast(e.message, 'error'))
    api.get('/admin/settings').then(setSettings).catch(() => {})
  }, [toast])
  useEffect(load, [load])

  if (!data) return <Spinner />

  const add = (path, transform = (f) => f) => async (form) => {
    try {
      await api.post(path, transform(form))
      toast('Added', 'success')
      load()
    } catch (err) {
      toast(err.message, 'error')
    }
  }
  const toggle = (kind) => async (item) => {
    try {
      await api.post(`/admin/${kind}/${item.id}/toggle`)
      load()
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const saveSettings = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.put('/admin/settings', { settings })
      toast('Settings saved', 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const settingDefs = [
    ['company_name', 'Company name'],
    ['office_start', 'Office start time (HH:MM)'],
    ['office_end', 'Office end time (HH:MM)'],
    ['late_after', 'Mark late after (HH:MM)'],
  ]

  return (
    <div className="grid cols-2" style={{ alignItems: 'start' }}>
      <ItemList title="Departments" items={data.departments} nameKey="name"
                addFields={[{ key: 'name', placeholder: 'New department name' }]}
                onAdd={add('/admin/departments')} onToggle={toggle('departments')} />
      <ItemList title="Designations" items={data.designations} nameKey="title"
                addFields={[{ key: 'name', placeholder: 'New designation title' }]}
                onAdd={add('/admin/designations')} onToggle={toggle('designations')} />
      <ItemList title="Office Locations" items={data.locations} nameKey="name"
                extra={(i) => i.address || ''}
                addFields={[{ key: 'name', placeholder: 'Branch name' },
                            { key: 'address', placeholder: 'Address', required: false }]}
                onAdd={add('/admin/locations')} onToggle={toggle('locations')} />
      <ItemList title="Shifts" items={data.shifts} nameKey="name"
                extra={(i) => `${i.start_time} – ${i.end_time}`}
                addFields={[{ key: 'name', placeholder: 'Shift name' },
                            { key: 'start_time', placeholder: 'Start', type: 'time' },
                            { key: 'end_time', placeholder: 'End', type: 'time' }]}
                onAdd={add('/admin/shifts')} onToggle={toggle('shifts')} />
      {settings && (
        <div className="card">
          <div className="card-head"><h3>Company Settings</h3></div>
          <form className="card-body" onSubmit={saveSettings}>
            {settingDefs.map(([key, label]) => (
              <Field key={key} label={label}>
                <input className="input" value={settings[key] || ''}
                       onChange={(e) => setSettings({ ...settings, [key]: e.target.value })} />
              </Field>
            ))}
            <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Save Settings'}</button>
          </form>
        </div>
      )}
    </div>
  )
}
