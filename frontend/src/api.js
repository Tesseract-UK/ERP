// Minimal fetch-based API client with JWT handling.
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export const getToken = () => localStorage.getItem('hrms_token')
export const setToken = (t) => t ? localStorage.setItem('hrms_token', t) : localStorage.removeItem('hrms_token')

async function request(path, { method = 'GET', body, formData } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: formData || (body ? JSON.stringify(body) : undefined),
  })

  if (res.status === 401) {
    setToken(null)
    onUnauthorized()
    throw new Error('Session expired. Please sign in again.')
  }
  if (!res.ok) {
    let detail = 'Something went wrong'
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail
        : Array.isArray(data.detail) ? data.detail.map(d => d.msg).join(', ') : detail
    } catch { /* non-JSON error body */ }
    throw new Error(detail)
  }
  if (res.headers.get('content-type')?.includes('text/csv')) return res.blob()
  return res.status === 204 ? null : res.json()
}

export const api = {
  get: (path) => request(path),
  post: (path, body) => request(path, { method: 'POST', body }),
  put: (path, body) => request(path, { method: 'PUT', body }),
  del: (path) => request(path, { method: 'DELETE' }),
  postForm: (path, formData) => request(path, { method: 'POST', formData }),
}

// Trigger a CSV download from an authenticated endpoint.
export async function downloadCsv(path, filename) {
  const blob = await request(path)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// Current local time as an ISO string without timezone (what the API expects).
export const localNowIso = () => {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
