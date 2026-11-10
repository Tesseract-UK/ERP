import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { API_BASE } from '../api'
import { useAuth } from '../AuthContext'
import AuthShell, { AuthAlert, GoogleButton } from '../components/AuthShell'
import { Lock } from '../components/icons'

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
    <AuthShell
      eyebrow="Welcome back"
      title="Sign in to your workspace"
      subtitle="Use your Tesseract Google account to continue."
      footer={<>
        <p>New to Tesseract? <Link to="/signup">Create an account</Link></p>
        <p className="auth-admin"><Lock size={13} /> Administrator? <Link to="/admin">Sign in here</Link></p>
      </>}
    >
      <AuthAlert>{error}</AuthAlert>
      <GoogleButton onClick={handleGoogleLogin} busy={googleLoading}>Continue with Google</GoogleButton>
      <div className="auth-divider"><span>Only verified @tesseractuk.in accounts</span></div>
    </AuthShell>
  )
}
