import { createContext, useContext, useEffect, useState } from 'react'
import { api } from '../api/client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('user')
    return stored ? JSON.parse(stored) : null
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Revalidate the session on load if we have a token.
    const token = localStorage.getItem('access')
    if (token && !user) {
      api.get('/auth/me/')
        .then((res) => persist(res.data))
        .catch(() => localStorage.clear())
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function persist(u) {
    setUser(u)
    localStorage.setItem('user', JSON.stringify(u))
  }

  async function login(email, password) {
    const { data } = await api.post('/auth/login/', { email, password })
    localStorage.setItem('access', data.access)
    localStorage.setItem('refresh', data.refresh)
    persist(data.user)
    return data.user
  }

  async function register(payload) {
    const { data } = await api.post('/auth/register/', payload)
    localStorage.setItem('access', data.access)
    localStorage.setItem('refresh', data.refresh)
    persist(data.user)
    return data.user
  }

  function logout() {
    // Server blacklists the refresh token so it can't be reused after logout.
    // Tokens are read now because storage is cleared before the request goes out.
    const access = localStorage.getItem('access')
    const refresh = localStorage.getItem('refresh')
    if (access) {
      api.post('/auth/logout/', { refresh }, { headers: { Authorization: `Bearer ${access}` }, _retried: true })
        .catch(() => {})
    }
    localStorage.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, updateUser: persist }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
