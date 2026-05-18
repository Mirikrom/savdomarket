import axios from 'axios'

import { markApiUnreachable } from '../offline/connectivity'

// Default: relative `/api/v1` — Vite dev server proxy orqali backend'ga uzatadi
// (vite.config.js'dagi server.proxy ga qarang). Production'da odatda nginx
// shunday proxy qiladi. Maxsus override kerak bo'lsa VITE_API_BASE_URL ni env'da
// belgilang.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 20000,
  headers: { 'Content-Type': 'application/json' },
})

// Persisted current organization id (selected by the user) — read on every
// request so swapping orgs is instant.
function getOrganizationId() {
  return localStorage.getItem('organization_id') || ''
}

api.interceptors.request.use((config) => {
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type']
  }
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  // Provider (super admin) so'rovlari uchun organization context kerak emas;
  // X-Skip-Org header yoki /provider/ url prefiksi orqali bilamiz.
  const skipOrg =
    config.headers?.['X-Skip-Org'] === '1' ||
    (typeof config.url === 'string' && config.url.startsWith('/provider/'))
  if (!skipOrg) {
    const orgId = getOrganizationId()
    if (orgId) config.headers['X-Organization-Id'] = orgId
  }
  if (config.headers) delete config.headers['X-Skip-Org']
  return config
})

// --- Token refresh on 401 ----------------------------------------------------
// If the access token has expired we attempt to refresh it once. Concurrent
// requests are queued so we only fire a single /token/refresh/ call.

let isRefreshing = false
let pendingQueue = []

function processQueue(error, token = null) {
  pendingQueue.forEach(({ resolve, reject }) => {
    if (error) reject(error)
    else resolve(token)
  })
  pendingQueue = []
}

/** Joriy origin bilan (masalan HTTPS dev) — protokol/host mos bo‘lishi uchun */
function redirectToLogin() {
  try {
    window.location.replace(new URL('/auth/login', window.location.href).href)
  } catch {
    window.location.replace('/auth/login')
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status
    if (!error.response || status === 502 || status === 503 || status === 504) {
      markApiUnreachable()
    }
    const original = error.config

    if (status !== 401 || original?._retried || original?.url?.includes('/auth/token/refresh/')) {
      return Promise.reject(error)
    }

    const refresh = localStorage.getItem('refresh_token')
    if (!refresh) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      redirectToLogin()
      return Promise.reject(error)
    }

    if (isRefreshing) {
      return new Promise((resolve, reject) => {
        pendingQueue.push({ resolve, reject })
      }).then((token) => {
        original.headers.Authorization = `Bearer ${token}`
        original._retried = true
        return api(original)
      })
    }

    isRefreshing = true
    try {
      const { data } = await axios.post(`${BASE_URL}/auth/token/refresh/`, { refresh })
      if (data.access) localStorage.setItem('access_token', data.access)
      if (data.refresh) localStorage.setItem('refresh_token', data.refresh)
      processQueue(null, data.access)
      original.headers.Authorization = `Bearer ${data.access}`
      original._retried = true
      return api(original)
    } catch (refreshError) {
      processQueue(refreshError, null)
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      localStorage.removeItem('organization_id')
      redirectToLogin()
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  },
)

export default api
