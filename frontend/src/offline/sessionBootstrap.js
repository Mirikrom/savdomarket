import { checkApiReachable, isOfflineMode } from './connectivity'
import {
  hydrateAuthFromOfflineSnapshot,
  hydrateOrganizationStore,
  saveCashierSnapshot,
} from './posContext'

/** Token bor, lekin server ishlamasa — keshdan sessiya tiklash. */
export async function bootstrapOfflineSession(authStore, orgStore) {
  const token = localStorage.getItem('access_token')
  if (!token) return { ok: false, reason: 'no_token' }

  await hydrateAuthFromOfflineSnapshot(authStore)

  const role = localStorage.getItem('user_role')
  const orgId = localStorage.getItem('organization_id')
  const branchId = localStorage.getItem('current_branch_id')
  if (role) authStore.role = role
  if (orgId) authStore.organizationId = Number(orgId) || null
  if (branchId) authStore.branchId = Number(branchId) || null

  if (orgStore) {
    await hydrateOrganizationStore(orgStore)
  }

  authStore.loaded = true
  authStore.error = null
  return { ok: true, offline: isOfflineMode() }
}

/**
 * Ilova ochilganda: internet bo‘lsa serverdan, yo‘q bo‘lsa darhol lokal keshdan ishlaydi.
 */
export async function bootAuthenticatedApp(authStore, orgStore) {
  if (!localStorage.getItem('access_token')) {
    return { ok: false, reason: 'no_token' }
  }

  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    await checkApiReachable()
    return bootstrapOfflineSession(authStore, orgStore)
  }

  try {
    await authStore.fetchMe()
    await saveCashierSnapshot(authStore)
    if (orgStore) await orgStore.loadAll()
    return { ok: true, offline: false }
  } catch {
    await checkApiReachable()
    if (!authStore.isAuthenticated) {
      return { ok: false, reason: 'auth_failed' }
    }
    return bootstrapOfflineSession(authStore, orgStore)
  }
}
