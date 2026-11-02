import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { api } from '../api'
import { useAuth } from '../AuthContext'
import { Logo } from '../components/icons'

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
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-header">
          <Logo />
          <h1>Administrator sign in</h1>
          <p>Use your Tesseract administrator account</p>
        </div>

        {error && <div role="alert" className="login-error">{error}</div>}

        <form onSubmit={submit} style={{ display: 'grid', gap: 14 }}>
          <div className="field">
            <label htmlFor="admin-login-email">Email address</label>
            <input
              id="admin-login-email"
              className="input"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="admin@tesseractuk.in"
            />
          </div>
          <div className="field">
            <label htmlFor="admin-login-password">Password</label>
            <input
              id="admin-login-password"
              className="input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
            />
          </div>
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in as Admin'}
          </button>
        </form>

        <p style={{ textAlign: 'center', marginTop: 20, fontSize: 14 }}>
          Employee? <Link to="/login">Continue with Google</Link>
        </p>
      </div>
    </div>
  )
}
