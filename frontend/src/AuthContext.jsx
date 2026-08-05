// Bridges Clerk's session (who you are) to the HRMS profile (your role,
// department, onboarding state, etc.) that the rest of the app reads.
// Also recognizes the admin break-glass login (see AdminEmergencyLogin in
// Login.jsx), a parallel path that bypasses Clerk entirely.
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useAuth as useClerkAuth, useClerk } from '@clerk/clerk-react'
import { api, getLegacyToken, setLegacyToken, setUnauthorizedHandler } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const { isLoaded, isSignedIn } = useClerkAuth()
  const { signOut } = useClerk()
  const [user, setUser] = useState(null)
  const [profileLoading, setProfileLoading] = useState(true)
  const [authError, setAuthError] = useState('')

  const refresh = useCallback(() => {
    const legacy = getLegacyToken()
    if (!isSignedIn && !legacy) {
      setUser(null)
      setProfileLoading(false)
      return
    }
    setProfileLoading(true)
    api.get('/auth/me')
      .then((u) => { setUser(u); setAuthError('') })
      .catch((err) => {
        // Either Clerk accepted this identity but our backend won't sync a
        // profile for it (wrong email domain, deactivated account, etc), or
        // a stored break-glass token was rejected. Clear whichever path was
        // active — otherwise the route guard keeps bouncing to /login while
        // that session still looks "active", forming a redirect loop.
        setUser(null)
        setAuthError(err.message || 'Could not sign you in.')
        if (legacy) setLegacyToken(null)
        else signOut()
      })
      .finally(() => setProfileLoading(false))
  }, [isSignedIn, signOut])

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
  }, [])

  useEffect(() => {
    if (!isLoaded) return
    refresh()
  }, [isLoaded, refresh])

  const logout = () => {
    setUser(null)
    setLegacyToken(null)
    signOut()
  }

  return (
    <AuthContext.Provider value={{
      user, setUser, refresh, logout, authError,
      loading: !isLoaded || profileLoading,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
