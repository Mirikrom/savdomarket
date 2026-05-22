/** Backend `SubscriptionFeatureRequired` xabari (inglizcha). */
export const SUBSCRIPTION_FEATURE_EN =
  'Current subscription plan does not include this feature.'

export function extractApiDetail(error) {
  const data = error?.response?.data
  if (!data) return null
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) return data.detail[0]
  return null
}

export function isSubscriptionFeatureError(error) {
  return extractApiDetail(error) === SUBSCRIPTION_FEATURE_EN
}

/**
 * @param {unknown} error
 * @param {(key: string) => string} tr
 * @param {string} [fallback]
 */
export function resolveApiError(error, tr, fallback = '') {
  const detail = extractApiDetail(error)
  if (detail === SUBSCRIPTION_FEATURE_EN) {
    return tr('errors.subscriptionFeature')
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  const data = error?.response?.data
  if (data && typeof data === 'object') {
    const flat = Object.values(data).flat()
    const first = flat.find((x) => typeof x === 'string')
    if (first) return first
    const nested = flat.find((x) => Array.isArray(x))?.[0]
    if (typeof nested === 'string') return nested
  }
  if (typeof error?.message === 'string' && !error.message.startsWith('Request failed')) {
    return error.message
  }
  return fallback || tr('errors.generic')
}
