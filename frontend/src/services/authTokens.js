import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

/** Access token yangilash (probe va axios interceptor uchun). */
export async function refreshAccessToken() {
  const refresh = localStorage.getItem('refresh_token')
  if (!refresh) return null

  const { data } = await axios.post(`${BASE_URL}/auth/token/refresh/`, { refresh })
  if (data.access) localStorage.setItem('access_token', data.access)
  if (data.refresh) localStorage.setItem('refresh_token', data.refresh)
  return data.access || null
}
