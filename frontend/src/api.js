const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const TOKEN_KEY = 'hrms_admin_token'

export const getLegacyToken = () => localStorage.getItem(TOKEN_KEY)

export const setLegacyToken = (token) => {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

let onUnauthorized = () => {}

export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn
}

async function request(path, { method = 'GET', body, formData } = {}) {
  const headers = {}
  const token = getLegacyToken()

  // Every role uses the same Bearer-token mechanism.
  // The backend determines the user's identity and permissions.
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  if (body !== undefined && body !== null) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: formData || (
      body !== undefined && body !== null
        ? JSON.stringify(body)
        : undefined
    ),
  })

  if (response.status === 401) {
    const endpoint = path.split('?')[0]

    const isPublicAuthEndpoint = [
      '/auth/login',
      '/auth/signup',
      '/auth/google/login',
      '/auth/google/callback',
    ].includes(endpoint)

    if (!isPublicAuthEndpoint) {
      setLegacyToken(null)
      onUnauthorized()
    }

    let detail = 'Session expired. Please sign in again.'

    try {
      const data = await response.json()

      if (typeof data.detail === 'string') {
        detail = data.detail
      } else if (Array.isArray(data.detail)) {
        detail = data.detail.map((item) => item.msg).join(', ')
      }
    } catch {
      // Keep the default error message if the response is not JSON.
    }

    throw new Error(detail)
  }

  if (!response.ok) {
    let detail = 'Something went wrong'

    try {
      const data = await response.json()

      if (typeof data.detail === 'string') {
        detail = data.detail
      } else if (Array.isArray(data.detail)) {
        detail = data.detail.map((item) => item.msg).join(', ')
      }
    } catch {
      // Keep the default message if the response is not JSON.
    }

    throw new Error(detail)
  }

  if (response.headers.get('content-type')?.includes('text/csv')) {
    return response.blob()
  }

  if (response.status === 204) {
    return null
  }

  return response.json()
}

export const api = {
  get: (path) => request(path),

  post: (path, body) =>
    request(path, {
      method: 'POST',
      body,
    }),

  put: (path, body) =>
    request(path, {
      method: 'PUT',
      body,
    }),

  del: (path) =>
    request(path, {
      method: 'DELETE',
    }),

  postForm: (path, formData) =>
    request(path, {
      method: 'POST',
      formData,
    }),
}

export async function downloadCsv(path, filename) {
  const blob = await request(path)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')

  anchor.href = url
  anchor.download = filename
  anchor.click()

  URL.revokeObjectURL(url)
}

export const localNowIso = () => {
  const date = new Date()

  const pad = (value) => String(value).padStart(2, '0')

  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}