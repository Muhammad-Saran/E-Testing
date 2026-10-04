import axios from 'axios'

// Same origin by default (Django serves the built app); set VITE_API_URL for the Vite dev server.
const API_URL = import.meta.env.VITE_API_URL || '/api'

export const api = axios.create({ baseURL: API_URL })

// Attach the JWT access token to every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On a 401, try a single silent refresh, then replay the original request.
let refreshing = null
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    const refresh = localStorage.getItem('refresh')
    if (error.response?.status === 401 && refresh && !original._retried) {
      original._retried = true
      try {
        refreshing = refreshing || axios.post(`${API_URL}/auth/refresh/`, { refresh })
        const { data } = await refreshing
        refreshing = null
        localStorage.setItem('access', data.access)
        // Refresh tokens rotate: the old one is blacklisted, so keep the new one.
        if (data.refresh) localStorage.setItem('refresh', data.refresh)
        original.headers.Authorization = `Bearer ${data.access}`
        return api(original)
      } catch (e) {
        refreshing = null
        localStorage.clear()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)
