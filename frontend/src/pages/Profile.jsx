// Self-service profile: editable contact fields, read-only sensitive data.
import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import { Field, PasswordInput, Spinner, fmtDate, titleCase, useToast } from '../components/ui'

function ReadRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '9px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ color: 'var(--ink-2)' }}>{label}</span>
      <strong style={{ textAlign: 'right' }}>{value || '—'}</strong>
    </div>
  )
}

export default function Profile() {
  const toast = useToast()
  const { user } = useAuth()
  const [profile, setProfile] = useState(null)
  const [form, setForm] = useState({})
  const [pw, setPw] = useState({ current_password: '', new_password: '' })
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.get('/profile').then((p) => {
      setProfile(p)
      setForm({ phone: p.phone || '', address: p.address || '',
                emergency_contact_name: p.emergency_contact_name || '',
                emergency_contact_phone: p.emergency_contact_phone || '' })
    }).catch((e) => toast(e.message, 'error'))
  }, [toast])

  if (!profile) return <Spinner />

  const saveProfile = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const p = await api.put('/profile', form)
      setProfile(p)
      toast('Profile updated', 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const changePassword = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.post('/auth/change-password', pw)
      setPw({ current_password: '', new_password: '' })
      toast('Password changed successfully', 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const requestPasswordChange = async () => {
    setBusy(true)
    try {
      const res = await api.post('/auth/password-change-request')
      toast(res.message, 'success')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid cols-2" style={{ alignItems: 'start' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card">
          <div className="card-head"><h3>Employment Details</h3><span className="badge neutral">Managed by HR</span></div>
          <div className="card-body">
            <ReadRow label="Employee ID" value={profile.employee_code} />
            <ReadRow label="Full name" value={profile.full_name} />
            <ReadRow label="Email" value={profile.email} />
            <ReadRow label="Role" value={titleCase(profile.role)} />
            <ReadRow label="Department" value={profile.department} />
            <ReadRow label="Designation" value={profile.designation} />
            <ReadRow label="Reporting manager" value={profile.manager_name} />
            <ReadRow label="Joining date" value={fmtDate(profile.joining_date)} />
            <ReadRow label="Date of birth" value={fmtDate(profile.date_of_birth)} />
          </div>
        </div>
        <div className="card">
          <div className="card-head"><h3>Financial & Identity</h3><span className="badge neutral">Read-only</span></div>
          <div className="card-body">
            <ReadRow label="PAN number" value={profile.pan_number} />
            <ReadRow label="Aadhaar number" value={profile.aadhaar_number} />
            <ReadRow label="Passport" value={profile.passport_number} />
            <ReadRow label="Bank account" value={profile.bank_account} />
            <ReadRow label="IFSC code" value={profile.ifsc_code} />
            <p className="help-text" style={{ marginTop: 10 }}>
              Sensitive values are masked. Contact HR to correct any of these details.
            </p>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div className="card">
          <div className="card-head"><h3>Contact Information</h3><span className="badge ok">Editable</span></div>
          <form className="card-body" onSubmit={saveProfile}>
            <Field label="Phone number">
              <input className="input" value={form.phone} maxLength={20}
                     onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            </Field>
            <Field label="Address">
              <textarea className="input" value={form.address}
                        onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </Field>
            <div className="form-row">
              <Field label="Emergency contact name">
                <input className="input" value={form.emergency_contact_name}
                       onChange={(e) => setForm({ ...form, emergency_contact_name: e.target.value })} />
              </Field>
              <Field label="Emergency contact phone">
                <input className="input" value={form.emergency_contact_phone} maxLength={20}
                       onChange={(e) => setForm({ ...form, emergency_contact_phone: e.target.value })} />
              </Field>
            </div>
            <button className="btn" disabled={busy}>{busy ? 'Saving…' : 'Save Changes'}</button>
          </form>
        </div>
        <div className="card">
          <div className="card-head"><h3>Password</h3></div>
          {user.role === 'admin' ? (
            <form className="card-body" onSubmit={changePassword}>
              <Field label="Current password" required>
                <PasswordInput required autoComplete="current-password"
                       value={pw.current_password}
                       onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
              </Field>
              <Field label="New password" required help="At least 8 characters">
                <PasswordInput required minLength={8} autoComplete="new-password"
                       value={pw.new_password}
                       onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
              </Field>
              <button className="btn" disabled={busy}>Update Password</button>
            </form>
          ) : (
            <div className="card-body">
              <p style={{ color: 'var(--ink-2)', marginBottom: 12 }}>
                Company policy: password changes need administrator approval.
                Send a request, and once an admin approves it you will be asked to
                set a new password at your next sign-in.
              </p>
              <button className="btn secondary" disabled={busy} onClick={requestPasswordChange}>
                {busy ? 'Sending…' : 'Request Password Change'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
