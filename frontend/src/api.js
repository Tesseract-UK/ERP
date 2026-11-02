const configuredApiBase = import.meta.env.VITE_API_URL?.trim()
export const API_BASE = (() => {
  const base = configuredApiBase || (import.meta.env.DEV ? 'http://localhost:8000' : '')
  if (!base) return ''
  try {
    const url = new URL(base)
    if (!['http:', 'https:'].includes(url.protocol)) return ''
    if (import.meta.env.PROD && url.protocol !== 'https:') return ''
    return base.replace(/\/+$/, '')
  } catch {
    return ''
  }
})()
const BASE = API_BASE

// Remove bearer tokens saved by earlier builds. Authentication now uses the
// HttpOnly server cookie, which JavaScript cannot read or accidentally expose.
try {
  localStorage.removeItem('hrms_admin_token')
} catch {
  // Storage may be unavailable in restricted browser contexts.
}

let onUnauthorized = () => {}
let refreshInFlight = null

const PUBLIC_AUTH_ENDPOINTS = new Set([
  '/auth/login',
  '/auth/admin/login',
  '/auth/signup',
  '/auth/google/login',
  '/auth/google/callback',
  '/auth/refresh',
  '/auth/logout',
])

export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn
}

async function refreshSession() {
  if (refreshInFlight) return refreshInFlight

  const refreshOnce = async () => {
    // Another tab may have refreshed the shared cookies while this tab waited.
    const currentSession = await fetch(`${BASE}/auth/me`, {
      credentials: 'include',
      cache: 'no-store',
    })
    if (currentSession.ok) return true

    const response = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      cache: 'no-store',
    })
    return response.ok
  }

  const refreshWithLock = async () => {
    if (globalThis.navigator?.locks?.request) {
      return navigator.locks.request('tesseract-hrms-refresh', refreshOnce)
    }
    return refreshOnce()
  }

  refreshInFlight = refreshWithLock()
    .catch(() => false)
    .finally(() => {
      refreshInFlight = null
    })

  return refreshInFlight
}

async function request(path, { method = 'GET', body, formData } = {}, hasRetried = false) {
  if (!BASE) {
    throw new Error('HRMS API URL is not configured for this deployment.')
  }

  const headers = {}

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
    const isPublicAuthEndpoint = PUBLIC_AUTH_ENDPOINTS.has(endpoint)

    if (!isPublicAuthEndpoint && !hasRetried) {
      const renewed = await refreshSession()
      if (renewed) {
        return request(path, { method, body, formData }, true)
      }
    }

    if (!isPublicAuthEndpoint) {
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
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const localNowIso = () => {
  const date = new Date()

  const pad = (value) => String(value).padStart(2, '0')

  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
  )
}
