import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

import {
  api,
  getLegacyToken,
  setLegacyToken,
  setUnauthorizedHandler,
} from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [profileLoading, setProfileLoading] = useState(true)
  const [authError, setAuthError] = useState('')

  const refresh = useCallback(async () => {
    setProfileLoading(true)

    console.log(
  'Token before /auth/me:',
  getLegacyToken() ? 'PRESENT' : 'MISSING'
)
console.log('Calling /auth/me')

    try {
      const currentUser = await api.get('/auth/me')

      setUser(currentUser)
      setAuthError('')

      return currentUser
    } catch {
      // A logged-out visitor may receive 401 from /auth/me.
      setUser(null)
      setAuthError('')

      if (getLegacyToken()) {
        setLegacyToken(null)
      }

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
    setLegacyToken(null)

    try {
      await api.post('/auth/logout')
    } catch {
      // Clear the local session even if the request fails.
    } finally {
      window.location.assign('/login')
    }
  }, [])

  const login = useCallback(
    async (credentials) => {
      setAuthError('')

      try {
        const result = await api.post('/auth/login', credentials)

        if (!result?.access_token || !result?.user) {
          throw new Error('Invalid login response from the server.')
        }

        setLegacyToken(result.access_token)
        setUser(result.user)

        return result.user
      } catch (error) {
        setAuthError(error.message || 'Login failed.')
        throw error
      }
    },
    [],
  )

  return (
    <AuthContext.Provider
      value={{
        user,
        setUser,
        refresh,
        login,
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