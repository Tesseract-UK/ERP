
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { API_BASE } from '../api'
import AuthShell, { AuthAlert, GoogleButton } from '../components/AuthShell'

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
    <AuthShell
      eyebrow="Join your team"
      title="Create your account"
      subtitle="Sign up with your company Google account. HR will finish setting you up and assign your manager."
      footer={<p>Already have an account? <Link to="/login">Sign in</Link></p>}
    >
      <AuthAlert>{error || authError}</AuthAlert>
      <GoogleButton onClick={startGoogleSignup} busy={startingGoogleLogin}>Sign up with Google</GoogleButton>
      <div className="auth-divider"><span>Only verified @tesseractuk.in accounts</span></div>
    </AuthShell>
  )
}
