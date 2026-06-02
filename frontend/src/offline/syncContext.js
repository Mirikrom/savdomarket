import { hydrateOrganizationStore, saveOrganizationSnapshot } from './posContext'

/** Sinxron oldidan organization_id (API header) borligini ta'minlash. */
export async function ensureSyncOrgContext(orgStore) {
  let orgId = localStorage.getItem('organization_id')
  if (orgId) return Number(orgId)

  if (orgStore) {
    await hydrateOrganizationStore(orgStore)
    await saveOrganizationSnapshot(orgStore).catch(() => {})
    orgId = localStorage.getItem('organization_id')
    if (orgId) return Number(orgId)
  }

  const { useAuthStore } = await import('../stores/auth')
  const auth = useAuthStore()
  if (!auth.loaded) {
    try {
      await auth.fetchMe()
    } catch {
      /* keyingi qadam */
    }
  }
  if (auth.organizationId) {
    auth.setCurrentOrganization(auth.organizationId)
    return Number(auth.organizationId)
  }

  return null
}
