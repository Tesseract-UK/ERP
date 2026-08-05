import { SignUp } from '@clerk/clerk-react'
import { dark } from '@clerk/themes'
import { useAuth } from '../AuthContext'
import { Logo } from '../components/icons'
import { clerkAppearance } from '../clerkAppearance'

export default function Signup() {
  const { authError } = useAuth()
  return (
    <div className="login-wrap">
      <div style={{ width: '100%', maxWidth: 400, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div className="logo" style={{ marginBottom: 22 }}><Logo size={20} /> Tesseract HRMS</div>
        {authError && (
          <div className="error-text" style={{ textAlign: 'center', marginBottom: 14 }}>{authError}</div>
        )}
        <SignUp routing="path" path="/signup" signInUrl="/login" fallbackRedirectUrl="/"
                appearance={{ baseTheme: dark, ...clerkAppearance }} />
      </div>
    </div>
  )
}
