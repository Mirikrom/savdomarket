import { refreshAccessToken } from '../services/authTokens'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/** Brauzer onlayn bo‘lsa, API tekshiruvigacha optimistik onlayn (prod da «offline→onlayn» sakrashini kamaytiradi). */
let apiReachable = typeof navigator !== 'undefined' ? navigator.onLine : false
let lastNotifiedOffline = typeof navigator !== 'undefined' ? !navigator.onLine : true
let probeInFlight = null
/** Access muddati tugagach refresh ham ishlamasa — 15s da 401 spam bo‘lmasin */
let probeAuthPaused = false

const listeners = new Set()

function isBrowserOffline() {
  return typeof navigator !== 'undefined' && !navigator.onLine
}

function isApiUpStatus(status) {
  if (!status) return false
  if (status === 502 || status === 503 || status === 504) return false
  return status >= 200 && status < 500
}

export function isOfflineMode() {
  if (isBrowserOffline()) return true
  return !apiReachable
}

export function isApiReachable() {
  return !isOfflineMode()
}

function notifyIfChanged() {
  const offline = isOfflineMode()
  if (offline === lastNotifiedOffline) return
  lastNotifiedOffline = offline

  listeners.forEach((fn) => {
    try {
      fn(offline)
    } catch {
      /* ignore */
    }
  })

  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent('savdopro:connectivity', { detail: { offline } })
    )
  }
}

/** Holat o‘zgarganda + yangi obuna bo‘lganda (joriy holat bilan). */
export function onConnectivityChange(fn) {
  listeners.add(fn)
  try {
    fn(isOfflineMode())
  } catch {
    /* ignore */
  }
  return () => listeners.delete(fn)
}

async function probeCategories(headers) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 5000)
  try {
    return await fetch(`${API_BASE}/categories/?page_size=1`, {
      method: 'GET',
      headers,
      signal: controller.signal,
      cache: 'no-store',
      credentials: 'same-origin',
    })
  } finally {
    clearTimeout(timer)
  }
}

export function resumeConnectivityProbe() {
  probeAuthPaused = false
}

export async function checkApiReachable() {
  if (probeInFlight) return probeInFlight

  probeInFlight = (async () => {
    if (isBrowserOffline()) {
      apiReachable = false
      notifyIfChanged()
      return false
    }

    if (probeAuthPaused) {
      return apiReachable
    }

    let token = localStorage.getItem('access_token')
    if (!token) {
      apiReachable = false
      notifyIfChanged()
      return false
    }

    const orgId = localStorage.getItem('organization_id')
    const headers = { Accept: 'application/json', Authorization: `Bearer ${token}` }
    if (orgId) headers['X-Organization-Id'] = orgId

    try {
      let res = await probeCategories(headers)

      if (res.status === 401) {
        try {
          const access = await refreshAccessToken()
          if (access) {
            headers.Authorization = `Bearer ${access}`
            res = await probeCategories(headers)
          }
        } catch {
          probeAuthPaused = true
          apiReachable = true
          notifyIfChanged()
          return true
        }
      }

      if (res.status === 401) {
        probeAuthPaused = true
        apiReachable = true
      } else {
        apiReachable = isApiUpStatus(res.status)
      }
    } catch {
      apiReachable = false
    }

    notifyIfChanged()
    return apiReachable
  })().finally(() => {
    probeInFlight = null
  })

  return probeInFlight
}

export function markApiUnreachable() {
  if (!apiReachable) return
  apiReachable = false
  notifyIfChanged()
}

export function markApiReachable() {
  if (apiReachable) return
  apiReachable = true
  notifyIfChanged()
}

export function isNetworkError(error) {
  if (!error) return true
  const code = error.code
  if (code === 'ERR_NETWORK' || code === 'ECONNABORTED' || code === 'ETIMEDOUT') return true
  if (!error.response) return true
  return !isApiUpStatus(error.response.status)
}
