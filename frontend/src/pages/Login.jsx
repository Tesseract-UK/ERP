import { useState } from 'react'
import { useAuth } from '../AuthContext'
import { Field, PasswordInput } from '../components/ui'
import { Logo } from '../components/icons'

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
        <div className="logo"><Logo size={19} /> Tesseract HRMS</div>
        <div className="tag">Sign in to your workspace</div>
        <Field label="Email address" required>
          <input className="input" type="email" value={email} required autoFocus
                 autoComplete="username"
                 onChange={(e) => setEmail(e.target.value)} placeholder="you@tesseractuk.in" />
        </Field>
        <Field label="Password" required error={error}>
          <PasswordInput value={password} required
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
