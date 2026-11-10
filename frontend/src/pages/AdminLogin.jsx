import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api'
import { useAuth } from '../AuthContext'
import AuthShell, { AuthAlert } from '../components/AuthShell'
import { PasswordInput } from '../components/ui'

export default function AdminLogin() {
  const navigate = useNavigate()
  const { user, refresh } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (user) navigate('/', { replace: true })
  }, [user, navigate])

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api.post('/auth/admin/login', { email, password })
      const currentUser = await refresh()
      if (currentUser?.role !== 'admin') {
        setError('This sign-in page is only for administrators.')
        return
      }
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      eyebrow="Restricted"
      title="Administrator sign in"
      subtitle="Use your Tesseract administrator credentials."
      footer={<p>Not an administrator? <Link to="/login">Continue with Google</Link></p>}
    >
      <AuthAlert>{error}</AuthAlert>
      <form onSubmit={submit} className="auth-form">
        <div className="field">
          <label htmlFor="admin-login-email">Email address</label>
          <input id="admin-login-email" className="input" type="email" autoComplete="username" required
                 value={email} onChange={(event) => setEmail(event.target.value)} placeholder="admin@tesseractuk.in" />
        </div>
        <div className="field">
          <label htmlFor="admin-login-password">Password</label>
          <PasswordInput id="admin-login-password" autoComplete="current-password" required
                         value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" />
        </div>
        <button className="btn auth-submit" type="submit" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in as Admin'}
        </button>
      </form>
    </AuthShell>
  )
}
