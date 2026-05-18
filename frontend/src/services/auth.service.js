import api from './api'

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

function persistTokens(data) {
  if (data?.access) localStorage.setItem(ACCESS_KEY, data.access)
  if (data?.refresh) localStorage.setItem(REFRESH_KEY, data.refresh)
}

export function getAccessToken() {
  return localStorage.getItem(ACCESS_KEY)
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY)
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export async function login({ phone, password }) {
  const { data } = await api.post('/auth/login/', { phone, password })
  persistTokens(data)
  return data
}

export async function logout() {
  const refresh = getRefreshToken()
  try {
    if (refresh) await api.post('/auth/logout/', { refresh })
  } catch {
    /* ignore — we still clear local tokens */
  } finally {
    clearTokens()
  }
}

export async function registerRequestOtp(phone) {
  const { data } = await api.post('/auth/register/request-otp/', { phone })
  return data
}

export async function registerVerifyOtp({ phone, code }) {
  const { data } = await api.post('/auth/register/verify-otp/', { phone, code })
  return data
}

export async function registerComplete(payload) {
  const { data } = await api.post('/auth/register/complete/', payload)
  persistTokens(data)
  return data
}

export async function forgotPasswordRequest(phone) {
  const { data } = await api.post('/auth/password/forgot/', { phone })
  return data
}

export async function forgotPasswordVerify({ phone, code }) {
  const { data } = await api.post('/auth/password/verify-code/', { phone, code })
  return data
}

export async function resetPassword({ reset_token, new_password }) {
  const { data } = await api.post('/auth/password/reset/', {
    reset_token,
    new_password,
  })
  return data
}

export async function fetchMe() {
  const { data } = await api.get('/accounts/me/')
  return data
}
