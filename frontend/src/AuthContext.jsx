import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

import {
  api,
  setUnauthorizedHandler,
} from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [profileLoading, setProfileLoading] = useState(true)
  const [authError, setAuthError] = useState('')

  const refresh = useCallback(async () => {
    setProfileLoading(true)

    try {
      const currentUser = await api.get('/auth/me')

      setUser(currentUser)
      setAuthError('')

      return currentUser
    } catch {
      // A logged-out visitor may receive 401 from /auth/me.
      setUser(null)
      setAuthError('')

      return null
    } finally {
      setProfileLoading(false)
    }
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null)
      setAuthError('')
    })

    refresh()

    return () => {
      setUnauthorizedHandler(() => {})
    }
  }, [refresh])

  const logout = useCallback(async () => {
    setUser(null)
    setAuthError('')

    try {
      await api.post('/auth/logout')
    } catch {
      // Clear the local session even if the request fails.
    } finally {
      window.location.assign('/login')
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        setUser,
        refresh,
        logout,
        authError,
        setAuthError,
        loading: profileLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }

  return context
}
