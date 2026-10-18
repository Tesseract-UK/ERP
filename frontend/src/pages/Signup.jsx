
import { useState } from 'react'
import { useAuth } from '../AuthContext'
import { Logo } from '../components/icons'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function Signup() {
  const { authError } = useAuth()
  const [startingGoogleLogin, setStartingGoogleLogin] = useState(false)

  const startGoogleSignup = () => {
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
          Continue with your company Google account to access HRMS.
        </p>

        {authError && (
          <div
            className="error-text"
            style={{ textAlign: 'center', marginBottom: 14 }}
          >
            {authError}
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
          <a href="/login">Sign in</a>
        </p>
      </div>
    </div>
  )
}
