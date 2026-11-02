
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { API_BASE } from '../api'
import { Logo } from '../components/icons'

export default function Signup() {
  const { authError } = useAuth()
  const [startingGoogleLogin, setStartingGoogleLogin] = useState(false)
  const [error, setError] = useState('')

  const startGoogleSignup = () => {
    if (!API_BASE) {
      setError('HRMS signup is unavailable because the API URL is not configured.')
      return
    }
    setError('')
    setStartingGoogleLogin(true)
    window.location.assign(`${API_BASE}/auth/google/login`)
  }

  return (
    <div className="login-wrap">
      <div
        style={{
          width: '100%',
          maxWidth: 400,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
        }}
      >
        <div className="logo" style={{ marginBottom: 22 }}>
          <Logo size={24} />
          <span>Tesseract HRMS</span>
        </div>

        <h2 style={{ margin: '0 0 8px', textAlign: 'center' }}>
          Get started
        </h2>

        <p
          className="help-text"
          style={{ marginBottom: 22, textAlign: 'center' }}
        >
          Use an active, verified Google account ending in @tesseractuk.in. Other email domains are not allowed.
        </p>

        {(error || authError) && (
          <div
            role="alert"
            className="error-text"
            style={{ textAlign: 'center', marginBottom: 14 }}
          >
            {error || authError}
          </div>
        )}

        <button
          type="button"
          className="btn secondary"
          onClick={startGoogleSignup}
          disabled={startingGoogleLogin}
          style={{
            width: '100%',
            minHeight: 44,
            fontSize: 14,
            gap: 10,
          }}
        >
          <span
            aria-hidden="true"
            style={{
              background: '#fff',
              color: '#4285F4',
              borderRadius: 4,
              width: 22,
              height: 22,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 700,
              fontSize: 15,
            }}
          >
            G
          </span>

          {startingGoogleLogin
            ? 'Redirecting to Google…'
            : 'Sign up with Google'}
        </button>

        <p className="help-text" style={{ marginTop: 20, textAlign: 'center' }}>
          Already have an account?{' '}
          <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
