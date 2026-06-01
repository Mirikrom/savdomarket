const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/** Brauzer onlayn bo‘lsa, API tekshiruvigacha optimistik onlayn (prod da «offline→onlayn» sakrashini kamaytiradi). */
let apiReachable = typeof navigator !== 'undefined' ? navigator.onLine : false
let lastNotifiedOffline = typeof navigator !== 'undefined' ? !navigator.onLine : true
let probeInFlight = null

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

export async function checkApiReachable() {
  if (probeInFlight) return probeInFlight

  probeInFlight = (async () => {
    const token = localStorage.getItem('access_token')

    if (isBrowserOffline()) {
      apiReachable = false
      notifyIfChanged()
      return false
    }

    if (!token) {
      apiReachable = false
      notifyIfChanged()
      return false
    }

    const orgId = localStorage.getItem('organization_id')
    const headers = { Accept: 'application/json', Authorization: `Bearer ${token}` }
    if (orgId) headers['X-Organization-Id'] = orgId

    try {
      const controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 5000)
      const res = await fetch(`${API_BASE}/categories/?page_size=1`, {
        method: 'GET',
        headers,
        signal: controller.signal,
        cache: 'no-store',
        credentials: 'same-origin',
      })
      clearTimeout(timer)

      apiReachable = isApiUpStatus(res.status)
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
