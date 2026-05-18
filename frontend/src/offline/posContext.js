import { getMeta, normalizeOrgId, setMeta, toPlainJson } from './db'

const BRANCH_KEY = 'current_branch_id'
const CASHIER_NAME_KEY = 'cashier_display_name'

export function persistCashierName(name) {
  const n = String(name || '').trim()
  if (!n || typeof localStorage === 'undefined') return
  localStorage.setItem(CASHIER_NAME_KEY, n)
}

export function getPersistedCashierName() {
  if (typeof localStorage === 'undefined') return ''
  return localStorage.getItem(CASHIER_NAME_KEY) || ''
}

export function getOfflineCashierName(authStore) {
  const fromAuth =
    authStore?.fullName ||
    authStore?.user?.full_name ||
    authStore?.user?.phone ||
    authStore?.user?.username ||
    ''
  if (fromAuth) return fromAuth
  return getPersistedCashierName()
}

export async function resolveOfflineCashierName(authStore, payloadName = '') {
  if (payloadName) return String(payloadName).trim()
  const fromAuth = getOfflineCashierName(authStore)
  if (fromAuth) return fromAuth
  const snap = await getMeta('cashier_snapshot')
  return (
    snap?.full_name ||
    snap?.name ||
    snap?.username ||
    getPersistedCashierName() ||
    ''
  )
}

export async function hydrateAuthFromOfflineSnapshot(authStore) {
  if (!authStore) return

  const snap = await getMeta('cashier_snapshot')
  const name =
    snap?.full_name || snap?.name || snap?.username || getPersistedCashierName()

  if (name && !authStore.user?.full_name && !authStore.user?.phone) {
    authStore.user = {
      ...(authStore.user || {}),
      full_name: snap?.full_name || name,
      username: snap?.username || authStore.user?.username || '',
      phone: snap?.phone || authStore.user?.phone || '',
    }
  }

  const role = localStorage.getItem('user_role')
  const orgId = localStorage.getItem('organization_id')
  const branchId = localStorage.getItem(BRANCH_KEY)
  if (role && !authStore.role) authStore.role = role
  if (orgId && !authStore.organizationId) {
    authStore.organizationId = Number(orgId) || null
  }
  if (branchId && !authStore.branchId) {
    authStore.branchId = Number(branchId) || null
  }
}

function readOrgId(orgStore) {
  return normalizeOrgId(
    orgStore?.organization?.id ?? localStorage.getItem('organization_id')
  )
}

function readBranchId(orgStore) {
  return normalizeOrgId(orgStore?.currentBranchId ?? localStorage.getItem(BRANCH_KEY))
}

/** Kassa uchun org/filial — store, localStorage, IndexedDB meta. */
export async function resolvePosIds(orgStore) {
  let orgId = readOrgId(orgStore)
  let branchId = readBranchId(orgStore)

  if (!orgId || !branchId) {
    const catalog = await getMeta('catalog_sync')
    if (catalog) {
      orgId = orgId || normalizeOrgId(catalog.organizationId)
      branchId = branchId || normalizeOrgId(catalog.branchId)
    }
    const last = await getMeta('last_full_sync')
    if (last) {
      orgId = orgId || normalizeOrgId(last.organizationId)
      branchId = branchId || normalizeOrgId(last.branchId)
    }
  }

  if (orgId && !localStorage.getItem('organization_id')) {
    localStorage.setItem('organization_id', String(orgId))
  }
  if (branchId && !localStorage.getItem(BRANCH_KEY)) {
    localStorage.setItem(BRANCH_KEY, String(branchId))
  }

  return { orgId, branchId }
}

export async function hydrateOrganizationStore(orgStore) {
  if (!orgStore) return false

  const { orgId, branchId } = await resolvePosIds(orgStore)
  if (!orgId) return false

  let changed = false

  if (!orgStore.organization?.id) {
    const snap = await getMeta(`organization_${orgId}`)
    orgStore.organization = snap || { id: orgId, name: snap?.name || 'Tashkilot' }
    changed = true
  }

  if (!orgStore.branches?.length) {
    const branches = await getMeta(`branches_${orgId}`)
    if (Array.isArray(branches) && branches.length) {
      orgStore.branches = branches
      changed = true
    }
  }

  if (!orgStore.currentBranchId && branchId) {
    orgStore.currentBranchId = branchId
    changed = true
  }

  return changed
}

export async function saveCashierSnapshot(authStore) {
  try {
    const name = getOfflineCashierName(authStore)
    if (!name) return
    persistCashierName(name)
    await setMeta(
      'cashier_snapshot',
      toPlainJson({
        full_name: name,
        name,
        username: authStore?.user?.username || '',
        phone: authStore?.user?.phone || '',
      })
    )
  } catch (err) {
    console.warn('[offline] kassir snapshot saqlanmadi:', err)
  }
}

export async function saveOrganizationSnapshot(orgStore) {
  try {
    const org = orgStore?.organization
    if (!org?.id) return
    const orgId = normalizeOrgId(org.id)
    await setMeta(`organization_${orgId}`, {
      id: orgId,
      name: org.name || '',
      slug: org.slug,
    })
    localStorage.setItem('organization_id', String(orgId))
    if (orgStore.branches?.length) {
      await setMeta(`branches_${orgId}`, orgStore.branches)
    }
    if (orgStore.currentBranchId) {
      localStorage.setItem(BRANCH_KEY, String(orgStore.currentBranchId))
    }
  } catch (err) {
    console.warn('[offline] tashkilot snapshot saqlanmadi:', err)
  }
}
