const SUPPORT_MODE_KEY = 'support_mode'

export function isSupportModeActive() {
  return localStorage.getItem(SUPPORT_MODE_KEY) === '1'
}

/** Superuser mijoz do'koniga (owner huquqlari, o'z login). */
export async function enterClientStore(router, auth, orgStore, organization) {
  const orgId = Number(organization?.id)
  if (!Number.isFinite(orgId)) {
    throw new Error('Tashkilot tanlanmadi')
  }

  localStorage.setItem('is_provider', '1')
  localStorage.setItem(SUPPORT_MODE_KEY, '1')
  auth.setCurrentOrganization(orgId)

  await auth.fetchMe()
  if (orgStore) {
    await orgStore.loadAll()
  }

  router.push({ name: 'dashboard', query: { from_provider: '1' } })
}

/** Provider admin panelga qaytish (do'kon kontekstini tozalash). */
export function exitToProviderPanel(router, auth) {
  localStorage.removeItem(SUPPORT_MODE_KEY)
  localStorage.removeItem('organization_id')
  localStorage.removeItem('current_branch_id')
  if (auth) {
    auth.organizationId = null
    auth.branchId = null
    auth.role = null
    auth.supportMode = false
  }
  router.push({ name: 'provider-dashboard' })
}

/** Superuser login — eski do'kon kontekstisiz provider panel. */
export function resetStoreContextForProvider() {
  localStorage.removeItem(SUPPORT_MODE_KEY)
  localStorage.removeItem('organization_id')
  localStorage.removeItem('current_branch_id')
}
