import { createContext, useContext, useEffect, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(!!getToken())

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null))
    if (getToken()) {
      api.get('/auth/me')
        .then(setUser)
        .catch(() => setToken(null))
        .finally(() => setLoading(false))
    }
  }, [])

  const login = async (email, password) => {
    const data = await api.post('/auth/login', { email, password })
    setToken(data.access_token)
    setUser(data.user)
  }

  const logout = () => {
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, setUser, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
