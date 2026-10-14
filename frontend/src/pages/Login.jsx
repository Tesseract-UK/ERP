import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { api, setLegacyToken } from '../api'
import { useAuth } from '../AuthContext'
import { Field, PasswordInput } from '../components/ui'
import { Logo } from '../components/icons'

const GOOGLE_ERRORS = {
  google_not_configured:
    'Google login abhi configure nahi hua hai. Email aur password se login karo.',
  google_login_cancelled:
    'Google login cancel ho gaya. Dobara try karo.',
  google_login_incomplete:
    'Google login complete nahi hua. Dobara try karo.',
  google_state_invalid:
    'Google login session verify nahi ho paya. Dobara try karo.',
  google_login_failed:
    'Google login failed. Dobara try karo ya email-password use karo.',
  google_account_mismatch:
    'Ye Google account HRMS account se match nahi karta.',
  email_domain_not_allowed:
    'Is email domain ko login karne ki permission nahi hai.',
  account_deactivated:
    'Tumhara account deactivate hai. HR ya Admin se contact karo.',
}

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user, setUser, setAuthError } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)

  useEffect(() => {
    const code = searchParams.get('error')

    if (code) {
      setError(
        GOOGLE_ERRORS[code] ||
          'Login nahi ho paya. Dobara try karo.',
      )
    }
  }, [searchParams])

  // Reset Google loading when returning to this page with Back/Forward.
  useEffect(() => {
    const resetGoogleLoading = () => {
      setGoogleLoading(false)
    }

    window.addEventListener('pageshow', resetGoogleLoading)

    return () => {
      window.removeEventListener('pageshow', resetGoogleLoading)
    }
  }, [])

  useEffect(() => {
    if (user) {
      navigate('/', { replace: true })
    }
  }, [user, navigate])

  const handleLogin = async (event) => {
    event.preventDefault()

    setError('')
    setAuthError('')
    setLoading(true)

    try {
      const result = await api.post('/auth/login', {
        email: email.trim().toLowerCase(),
        password,
      })

      if (!result?.access_token || !result?.user) {
        throw new Error('Server se valid login response nahi mila.')
      }

      setLegacyToken(result.access_token)
      setUser(result.user)

      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed. Dobara try karo.')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleLogin = () => {
    setError('')
    setGoogleLoading(true)

    const apiBase =
      import.meta.env.VITE_API_URL || 'http://localhost:8000'

    window.location.assign(`${apiBase}/auth/google/login`)
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-header">
          <Logo />

          <h1>Welcome back</h1>

          <p>Sign in to your HRMS account</p>
        </div>

        {error && (
          <div
            role="alert"
            className="login-error"
            style={{
              marginBottom: '16px',
              padding: '12px',
              borderRadius: '8px',
              background: '#fff0f0',
              color: '#b42318',
              fontSize: '14px',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: '16px' }}>
            <Field label="Email address" required>
              <input
                className="input"
                type="email"
                name="email"
                autoComplete="username"
                placeholder="you@company.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </Field>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <Field label="Password" required>
              <PasswordInput
                name="password"
                autoComplete="current-password"
                placeholder="Enter your password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </Field>
          </div>

          <button
            type="submit"
            className="login-button"
            disabled={loading}
            style={{
              width: '100%',
              padding: '12px 16px',
              cursor: loading ? 'wait' : 'pointer',
            }}
          >
            {loading ? 'Signing in...' : 'Sign in with Email'}
          </button>
        </form>

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            margin: '22px 0',
          }}
        >
          <div
            style={{
              height: '1px',
              flex: 1,
              background: '#e5e7eb',
            }}
          />

          <span style={{ color: '#6b7280', fontSize: '13px' }}>
            OR
          </span>

          <div
            style={{
              height: '1px',
              flex: 1,
              background: '#e5e7eb',
            }}
          />
        </div>

        <button
          type="button"
          onClick={handleGoogleLogin}
          disabled={googleLoading}
          style={{
            width: '100%',
            padding: '12px 16px',
            border: '1px solid #d1d5db',
            borderRadius: '8px',
            background: '#ffffff',
            color: '#111827',
            cursor: googleLoading ? 'wait' : 'pointer',
            fontSize: '14px',
            fontWeight: 500,
          }}
        >
          {googleLoading
            ? 'Redirecting to Google...'
            : 'Continue with Google'}
        </button>

        <p
          style={{
            textAlign: 'center',
            marginTop: '20px',
            fontSize: '14px',
          }}
        >
          Don&apos;t have an account?{' '}
          <Link to="/signup">Create an account</Link>
        </p>
      </div>
    </div>
  )
}