import { useState } from 'react'
import { SignIn } from '@clerk/clerk-react'
import { dark } from '@clerk/themes'
import { api, setLegacyToken } from '../api'
import { useAuth } from '../AuthContext'
import { Field, PasswordInput } from '../components/ui'
import { Logo } from '../components/icons'
import { clerkAppearance } from '../clerkAppearance'

// Password-based fallback, admin accounts only — a working way in if Clerk
// or Google sign-in is ever unavailable. Bypasses Clerk entirely.
function AdminEmergencyLogin() {
  const { refresh } = useAuth()
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (!open) {
    return (
      <button type="button" className="btn ghost sm" style={{ marginTop: 18 }}
              onClick={() => setOpen(true)}>
        Admin emergency access
      </button>
    )
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const data = await api.post('/auth/login', { email: email.trim(), password })
      setLegacyToken(data.access_token)
      refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} style={{ marginTop: 18, width: '100%' }}>
      <p className="help-text" style={{ marginBottom: 10, textAlign: 'center' }}>
        Password-based fallback for admins only — everyone else should sign in above.
      </p>
      <Field label="Admin email" required>
        <input className="input" type="email" required autoFocus value={email}
               onChange={(e) => setEmail(e.target.value)} placeholder="you@tesseractuk.in" />
      </Field>
      <Field label="Password" required error={error}>
        <PasswordInput required value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <button className="btn secondary" style={{ width: '100%' }} disabled={busy}>
        {busy ? 'Signing in…' : 'Sign In'}
      </button>
    </form>
  )
}

export default function Login() {
  const { authError } = useAuth()
  return (
    <div className="login-wrap">
      <div style={{ width: '100%', maxWidth: 400, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div className="logo" style={{ marginBottom: 22 }}><Logo size={20} /> Tesseract HRMS</div>
        {authError && (
          <div className="error-text" style={{ textAlign: 'center', marginBottom: 14 }}>{authError}</div>
        )}
        <SignIn routing="path" path="/login" signUpUrl="/signup" fallbackRedirectUrl="/"
                appearance={{ baseTheme: dark, ...clerkAppearance }} />
        <AdminEmergencyLogin />
      </div>
    </div>
  )
}
