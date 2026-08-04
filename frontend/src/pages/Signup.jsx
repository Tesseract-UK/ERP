import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { Field, PasswordInput } from '../components/ui'
import { Logo } from '../components/icons'

export default function Signup() {
  const { signup } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await signup(fullName.trim(), email.trim(), password)
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
        <div className="tag">Create your workspace account</div>
        <Field label="Full name" required>
          <input className="input" type="text" value={fullName} required autoFocus
                 autoComplete="name"
                 onChange={(e) => setFullName(e.target.value)} placeholder="Your name" />
        </Field>
        <Field label="Email address" required>
          <input className="input" type="email" value={email} required
                 autoComplete="username"
                 onChange={(e) => setEmail(e.target.value)} placeholder="you@tesseractuk.in" />
        </Field>
        <Field label="Password" required error={error}
               help={!error ? 'At least 8 characters' : undefined}>
          <PasswordInput value={password} required minLength={8}
                 autoComplete="new-password"
                 onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </Field>
        <button className="btn" style={{ width: '100%', marginTop: 6 }} disabled={busy}>
          {busy ? 'Creating account…' : 'Sign Up'}
        </button>
        <div className="tag" style={{ marginTop: 14 }}>
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </form>
    </div>
  )
}
