// First-login wizard: one-time personal details. Authentication itself
// (password / Google) is handled by Clerk before the user ever reaches here.
import { useState } from 'react'
import { api } from '../api'
import { useAuth } from '../AuthContext'
import { Field, useToast } from '../components/ui'
import { CheckCircle2, Logo } from '../components/icons'

function DetailsStep({ onDone }) {
  const toast = useToast()
  const [form, setForm] = useState({
    phone: '', address: '', emergency_contact_name: '', emergency_contact_phone: '',
    date_of_birth: '', pan_number: '', aadhaar_number: '', passport_number: '',
    bank_account: '', ifsc_code: '',
  })
  const [busy, setBusy] = useState(false)
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const payload = { ...form }
      for (const k of Object.keys(payload)) if (payload[k] === '') payload[k] = null
      const user = await api.post('/profile/onboarding', payload)
      toast('Profile completed. Welcome to the team!', 'success')
      onDone(user)
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <h3 style={{ marginBottom: 4 }}>Tell us about yourself</h3>
      <p className="help-text" style={{ marginBottom: 16 }}>
        This is a one-time form. Identity and bank details become read-only after
        submission — contact HR for any later corrections.
      </p>
      <div className="form-row">
        <Field label="Phone number" required>
          <input className="input" required minLength={7} maxLength={20} value={form.phone}
                 onChange={(e) => set('phone', e.target.value)} />
        </Field>
        <Field label="Date of birth">
          <input className="input" type="date" value={form.date_of_birth}
                 onChange={(e) => set('date_of_birth', e.target.value)} />
        </Field>
      </div>
      <Field label="Residential address" required>
        <textarea className="input" required minLength={5} value={form.address}
                  onChange={(e) => set('address', e.target.value)} />
      </Field>
      <div className="form-row">
        <Field label="Emergency contact name" required>
          <input className="input" required minLength={2} value={form.emergency_contact_name}
                 onChange={(e) => set('emergency_contact_name', e.target.value)} />
        </Field>
        <Field label="Emergency contact phone" required>
          <input className="input" required minLength={7} maxLength={20}
                 value={form.emergency_contact_phone}
                 onChange={(e) => set('emergency_contact_phone', e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="PAN number">
          <input className="input" maxLength={20} value={form.pan_number}
                 onChange={(e) => set('pan_number', e.target.value.toUpperCase())} />
        </Field>
        <Field label="Aadhaar number (optional)">
          <input className="input" maxLength={20} value={form.aadhaar_number}
                 onChange={(e) => set('aadhaar_number', e.target.value)} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="Bank account number">
          <input className="input" maxLength={30} value={form.bank_account}
                 onChange={(e) => set('bank_account', e.target.value)} />
        </Field>
        <Field label="IFSC code">
          <input className="input" maxLength={15} value={form.ifsc_code}
                 onChange={(e) => set('ifsc_code', e.target.value.toUpperCase())} />
        </Field>
      </div>
      <Field label="Passport number (optional)">
        <input className="input" maxLength={30} value={form.passport_number}
               onChange={(e) => set('passport_number', e.target.value)} />
      </Field>
      <button className="btn" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Submitting…' : <>Complete Onboarding <CheckCircle2 size={15} /></>}
      </button>
    </form>
  )
}

export default function Onboarding() {
  const { user, setUser, logout } = useAuth()

  return (
    <div className="login-wrap">
      <div className="login-card" style={{ maxWidth: 520 }}>
        <div className="logo"><Logo size={19} /> Tesseract HRMS</div>
        <div className="tag">Welcome, {user.full_name} — let's get you set up</div>
        <DetailsStep onDone={setUser} />
        <button className="btn ghost sm" style={{ width: '100%', marginTop: 12 }} onClick={logout}>
          Sign out and continue later
        </button>
      </div>
    </div>
  )
}
