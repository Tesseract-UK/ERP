import { useState } from 'react'
import { useAuth } from '../AuthContext'
import { Field } from '../components/ui'

export default function Login() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(email.trim(), password)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <div className="logo">◈ Tesseract HRMS</div>
        <div className="tag">Sign in to your workspace</div>
        <Field label="Email address" required>
          <input className="input" type="email" value={email} required autoFocus
                 autoComplete="username"
                 onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
        </Field>
        <Field label="Password" required error={error}>
          <input className="input" type="password" value={password} required
                 autoComplete="current-password"
                 onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </Field>
        <button className="btn" style={{ width: '100%', marginTop: 6 }} disabled={busy}>
          {busy ? 'Signing in…' : 'Sign In'}
        </button>
      </form>
    </div>
  )
}
