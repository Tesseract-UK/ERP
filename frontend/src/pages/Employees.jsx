// HR employee management: list, add/edit, activate/deactivate, reset password.
import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import {
  ConfirmDialog, EmptyState, Field, Modal, Pagination, Spinner, titleCase, useToast,
} from '../components/ui'
import { useAuth } from '../AuthContext'

const EMPTY_FORM = {
  email: '', full_name: '', employee_code: '', password: '', role: 'employee',
  phone: '', department_id: '', designation_id: '', location_id: '', shift_id: '',
  manager_id: '', joining_date: '', date_of_birth: '', pan_number: '',
  aadhaar_number: '', passport_number: '', bank_account: '', ifsc_code: '',
  emergency_contact_name: '', emergency_contact_phone: '', address: '',
}

function EmployeeModal({ employeeId, orgData, onClose, onDone }) {
  const { user } = useAuth()
  const toast = useToast()
  const [form, setForm] = useState(EMPTY_FORM)
  const [loading, setLoading] = useState(!!employeeId)
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  useEffect(() => {
    if (!employeeId) return
    api.get(`/hr/employees/${employeeId}`).then((e) => {
      setForm({ ...EMPTY_FORM, ...Object.fromEntries(
        Object.keys(EMPTY_FORM).map((k) => [k, e[k] ?? '']) ), password: '' })
      setLoading(false)
    }).catch((err) => { toast(err.message, 'error'); onClose() })
  }, [employeeId, toast, onClose])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const payload = { ...form }
      for (const k of ['department_id', 'designation_id', 'location_id', 'shift_id', 'manager_id']) {
        payload[k] = payload[k] ? Number(payload[k]) : null
      }
      for (const k of Object.keys(payload)) if (payload[k] === '') payload[k] = null
      if (employeeId) {
        await api.put(`/hr/employees/${employeeId}`, payload)
        toast('Employee updated', 'success')
      } else {
        await api.post('/hr/employees', payload)
        toast('Employee created', 'success')
      }
      onDone()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <Modal title="Loading…" onClose={onClose}><Spinner /></Modal>

  const roles = user.role === 'admin' ? ['employee', 'manager', 'hr', 'admin'] : ['employee', 'manager', 'hr']

  return (
    <Modal wide title={employeeId ? 'Edit Employee' : 'Add Employee'} onClose={onClose} footer={
      <>
        <button className="btn secondary" onClick={onClose}>Cancel</button>
        <button className="btn" form="emp-form" disabled={busy}>{busy ? 'Saving…' : 'Save Employee'}</button>
      </>
    }>
      <form id="emp-form" onSubmit={submit}>
        <div className="form-row">
          <Field label="Full name" required>
            <input className="input" required value={form.full_name} onChange={(e) => set('full_name', e.target.value)} />
          </Field>
          <Field label="Email" required>
            <input className="input" type="email" required value={form.email} onChange={(e) => set('email', e.target.value)} />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Employee code" help={employeeId ? '' : 'Leave blank to auto-generate'}>
            <input className="input" value={form.employee_code} onChange={(e) => set('employee_code', e.target.value)} />
          </Field>
          <Field label={employeeId ? 'New password (leave blank to keep)' : 'Initial password'} required={!employeeId}>
            <input className="input" type="password" minLength={8} required={!employeeId}
                   autoComplete="new-password" value={form.password} onChange={(e) => set('password', e.target.value)} />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Role" required>
            <select className="input" value={form.role} onChange={(e) => set('role', e.target.value)}>
              {roles.map((r) => <option key={r} value={r}>{titleCase(r)}</option>)}
            </select>
          </Field>
          <Field label="Reporting manager">
            <select className="input" value={form.manager_id} onChange={(e) => set('manager_id', e.target.value)}>
              <option value="">— None —</option>
              {orgData.managers.filter((m) => m.id !== employeeId).map((m) =>
                <option key={m.id} value={m.id}>{m.full_name}</option>)}
            </select>
          </Field>
        </div>
        <div className="form-row">
          <Field label="Department">
            <select className="input" value={form.department_id} onChange={(e) => set('department_id', e.target.value)}>
              <option value="">— Select —</option>
              {orgData.departments.filter((d) => d.is_active).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
          </Field>
          <Field label="Designation">
            <select className="input" value={form.designation_id} onChange={(e) => set('designation_id', e.target.value)}>
              <option value="">— Select —</option>
              {orgData.designations.filter((d) => d.is_active).map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
          </Field>
        </div>
        <div className="form-row">
          <Field label="Office location">
            <select className="input" value={form.location_id} onChange={(e) => set('location_id', e.target.value)}>
              <option value="">— Select —</option>
              {orgData.locations.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
            </select>
          </Field>
          <Field label="Shift">
            <select className="input" value={form.shift_id} onChange={(e) => set('shift_id', e.target.value)}>
              <option value="">— Select —</option>
              {orgData.shifts.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.start_time}–{s.end_time})</option>)}
            </select>
          </Field>
        </div>
        <div className="form-row">
          <Field label="Joining date">
            <input className="input" type="date" value={form.joining_date} onChange={(e) => set('joining_date', e.target.value)} />
          </Field>
          <Field label="Date of birth">
            <input className="input" type="date" value={form.date_of_birth} onChange={(e) => set('date_of_birth', e.target.value)} />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Phone">
            <input className="input" value={form.phone} onChange={(e) => set('phone', e.target.value)} />
          </Field>
          <Field label="PAN number">
            <input className="input" value={form.pan_number} onChange={(e) => set('pan_number', e.target.value)} />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Aadhaar number (optional)">
            <input className="input" value={form.aadhaar_number} onChange={(e) => set('aadhaar_number', e.target.value)} />
          </Field>
          <Field label="Passport (optional)">
            <input className="input" value={form.passport_number} onChange={(e) => set('passport_number', e.target.value)} />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Bank account">
            <input className="input" value={form.bank_account} onChange={(e) => set('bank_account', e.target.value)} />
          </Field>
          <Field label="IFSC code">
            <input className="input" value={form.ifsc_code} onChange={(e) => set('ifsc_code', e.target.value)} />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Emergency contact name">
            <input className="input" value={form.emergency_contact_name} onChange={(e) => set('emergency_contact_name', e.target.value)} />
          </Field>
          <Field label="Emergency contact phone">
            <input className="input" value={form.emergency_contact_phone} onChange={(e) => set('emergency_contact_phone', e.target.value)} />
          </Field>
        </div>
        <Field label="Address">
          <textarea className="input" value={form.address} onChange={(e) => set('address', e.target.value)} />
        </Field>
      </form>
    </Modal>
  )
}

function ResetPasswordModal({ employee, onClose }) {
  const toast = useToast()
  const [pw, setPw] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.post(`/hr/employees/${employee.id}/reset-password`, { new_password: pw })
      toast(`Password reset for ${employee.full_name}`, 'success')
      onClose()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal title={`Reset password — ${employee.full_name}`} onClose={onClose} footer={
      <>
        <button className="btn secondary" onClick={onClose}>Cancel</button>
        <button className="btn" form="pw-form" disabled={busy}>{busy ? 'Resetting…' : 'Reset Password'}</button>
      </>
    }>
      <form id="pw-form" onSubmit={submit}>
        <Field label="New password" required help="At least 8 characters. Share it with the employee securely.">
          <input className="input" type="password" required minLength={8} value={pw}
                 autoComplete="new-password" onChange={(e) => setPw(e.target.value)} />
        </Field>
      </form>
    </Modal>
  )
}

export default function Employees() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [orgData, setOrgData] = useState(null)
  const [search, setSearch] = useState('')
  const [includeInactive, setIncludeInactive] = useState(false)
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState(null) // {type:'edit'|'new'|'reset'|'deactivate', ...}
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.get('/admin/org-data').then(setOrgData).catch(() => {}) }, [])

  const load = useCallback(() => {
    const params = new URLSearchParams({ page, page_size: 25 })
    if (search) params.append('search', search)
    if (includeInactive) params.append('include_inactive', 'true')
    api.get(`/hr/employees?${params}`).then(setData).catch((e) => toast(e.message, 'error'))
  }, [page, search, includeInactive, toast])
  useEffect(load, [load])

  const toggleActive = async (emp) => {
    setBusy(true)
    try {
      await api.post(`/hr/employees/${emp.id}/${emp.is_active ? 'deactivate' : 'activate'}`)
      toast(`${emp.full_name} ${emp.is_active ? 'deactivated' : 'reactivated'}`, 'success')
      setModal(null)
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
        <div><h2>Employees</h2><div className="sub">{data ? `${data.total} record(s)` : ''}</div></div>
        <button className="btn" onClick={() => setModal({ type: 'new' })}>+ Add Employee</button>
      </div>

      <div className="card pad toolbar">
        <input className="input" style={{ maxWidth: 280 }} placeholder="Search name, email or code…"
               value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }} />
        <label style={{ display: 'flex', gap: 6, alignItems: 'center', fontSize: 13 }}>
          <input type="checkbox" checked={includeInactive}
                 onChange={(e) => { setIncludeInactive(e.target.checked); setPage(1) }} />
          Show deactivated
        </label>
      </div>

      <div className="card">
        {data === null ? <Spinner /> : data.items.length === 0
          ? <EmptyState icon="🗂" title="No employees found" hint="Try a different search." />
          : (
            <>
              <div className="table-wrap"><table className="table">
                <thead><tr><th>Employee</th><th>Code</th><th>Department</th><th>Role</th>
                  <th>Manager</th><th>Status</th><th style={{ width: 210 }}>Actions</th></tr></thead>
                <tbody>
                  {data.items.map((e) => (
                    <tr key={e.id}>
                      <td><strong>{e.full_name}</strong><div className="help-text">{e.email}</div></td>
                      <td>{e.employee_code}</td>
                      <td>{e.department || '—'}</td>
                      <td>{titleCase(e.role)}</td>
                      <td>{e.manager_name || '—'}</td>
                      <td>{e.is_active ? <span className="badge ok">Active</span>
                                        : <span className="badge danger">Inactive</span>}</td>
                      <td>
                        <div className="toolbar" style={{ gap: 6 }}>
                          <button className="btn secondary sm" onClick={() => setModal({ type: 'edit', id: e.id })}>Edit</button>
                          <button className="btn ghost sm" onClick={() => setModal({ type: 'reset', emp: e })}>Reset PW</button>
                          <button className={`btn ghost sm`} style={{ color: e.is_active ? 'var(--danger)' : 'var(--ok)' }}
                                  onClick={() => setModal({ type: 'toggle', emp: e })}>
                            {e.is_active ? 'Deactivate' : 'Activate'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
            </>
          )}
      </div>

      {modal?.type === 'new' && orgData &&
        <EmployeeModal orgData={orgData} onClose={() => setModal(null)}
                       onDone={() => { setModal(null); load() }} />}
      {modal?.type === 'edit' && orgData &&
        <EmployeeModal employeeId={modal.id} orgData={orgData} onClose={() => setModal(null)}
                       onDone={() => { setModal(null); load() }} />}
      {modal?.type === 'reset' &&
        <ResetPasswordModal employee={modal.emp} onClose={() => setModal(null)} />}
      {modal?.type === 'toggle' &&
        <ConfirmDialog danger={modal.emp.is_active} busy={busy}
          title={`${modal.emp.is_active ? 'Deactivate' : 'Reactivate'} ${modal.emp.full_name}`}
          message={modal.emp.is_active
            ? 'The employee will immediately lose access to the system. Their records are preserved.'
            : 'The employee will regain access to the system.'}
          confirmLabel={modal.emp.is_active ? 'Deactivate' : 'Reactivate'}
          onConfirm={() => toggleActive(modal.emp)} onClose={() => setModal(null)} />}
    </div>
  )
}
