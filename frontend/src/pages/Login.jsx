import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { API_BASE } from '../api'
import { useAuth } from '../AuthContext'
import { Logo } from '../components/icons'

const GOOGLE_ERRORS = {
  google_not_configured:
    'Company Google sign-in is not configured on this server. Ask your administrator to configure Google OAuth, then restart the backend.',
  google_login_cancelled:
    'Google login was cancelled. You can try again.',
  google_login_incomplete:
    'Google login did not complete. You can try again.',
  google_state_invalid:
    'The Google login session could not be verified. Please try again.',
  google_login_failed:
    'Google login failed. Please try again or contact your administrator.',
  google_account_mismatch:
    'This Google account does not match the HRMS account.',
  email_domain_not_allowed:
    'Only a verified @tesseractuk.in account can access this organization.',
  account_deactivated:
    'This company email is linked to a deactivated HRMS account. Ask HR or an administrator to reactivate it.',
}

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user } = useAuth()
  const [error, setError] = useState('')
  const [googleLoading, setGoogleLoading] = useState(false)

  useEffect(() => {
    const code = searchParams.get('error')
    if (code) {
      setError(GOOGLE_ERRORS[code] || 'Google login failed. Please try again.')
    }
  }, [searchParams])

  useEffect(() => {
    const resetGoogleLoading = () => setGoogleLoading(false)
    window.addEventListener('pageshow', resetGoogleLoading)
    return () => window.removeEventListener('pageshow', resetGoogleLoading)
  }, [])

  useEffect(() => {
    if (user) navigate('/', { replace: true })
  }, [user, navigate])

  const handleGoogleLogin = () => {
    setError('')
    if (!API_BASE) {
      setError('HRMS sign-in is unavailable because the API URL is not configured.')
      return
    }
    setGoogleLoading(true)
    window.location.assign(`${API_BASE}/auth/google/login`)
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-header">
          <Logo />
          <h1>Welcome back</h1>
          <p>Sign in to your Tesseract HRMS account</p>
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
          {googleLoading ? 'Redirecting to Google…' : 'Continue with Google'}
        </button>

        <p
          style={{
            textAlign: 'center',
            marginTop: '20px',
            fontSize: '14px',
          }}
        >
          New to Tesseract?{' '}
          <Link to="/signup">Create an account</Link>
        </p>
        <p style={{ textAlign: 'center', marginTop: 12, fontSize: 13 }}>
          Administrator? <Link to="/admin">Sign in here</Link>
        </p>
      </div>
    </div>
  )
}
