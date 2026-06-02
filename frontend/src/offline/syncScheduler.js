import { checkApiReachable, isOfflineMode } from './connectivity'
import { syncAllOfflineData } from './fullSync'
import { syncOfflineSales } from './offlineSales'
import { syncOfflineStockReceipts } from './offlineStockReceipts'
import { ensureSyncOrgContext } from './syncContext'

const MIN_FULL_SYNC_MS = 3 * 60 * 1000

let fullSyncPromise = null
let lastSyncKey = ''
let lastSyncAt = 0
let pendingSyncPromise = null

function dispatchSyncComplete(detail) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('savdopro:sync-complete', { detail }))
  }
}

/** Kutilayotgan savdo, qarzdor/to'lov va kirimlarni serverga yuborish. */
export function runPendingOfflineSync() {
  if (pendingSyncPromise) return pendingSyncPromise

  pendingSyncPromise = (async () => {
    if (isOfflineMode()) {
      const ok = await checkApiReachable()
      if (!ok) return { skipped: true, offline: true }
    }

    const { useOrganizationStore } = await import('../stores/organization')
    const orgStore = useOrganizationStore()
    const orgId = await ensureSyncOrgContext(orgStore)
    if (!orgId) {
      const missing = {
        skipped: true,
        reason: 'no_organization',
        message: 'Tashkilot tanlanmagan. Sahifani yangilang yoki qayta kiring.',
      }
      dispatchSyncComplete(missing)
      return missing
    }

    const sales = await syncOfflineSales()
    const receipts = await syncOfflineStockReceipts().catch(() => ({ synced: 0, failed: 0 }))
    const result = { ...sales, receipts }
    dispatchSyncComplete(result)
    return result
  })()
    .catch((err) => {
      console.warn('[offline] sinxron:', err)
      const failed = { synced: 0, failed: 0, error: true }
      dispatchSyncComplete(failed)
      return failed
    })
    .finally(() => {
      pendingSyncPromise = null
    })

  return pendingSyncPromise
}

export function scheduleFullSync(organizationId, branchId, { branches, organization, force = false } = {}) {
  if (!organizationId || !branchId) return Promise.resolve({ skipped: true })
  if (isOfflineMode()) return Promise.resolve({ skipped: true, offline: true })

  const key = `${organizationId}:${branchId}`
  const now = Date.now()

  if (!force && fullSyncPromise) return fullSyncPromise
  if (!force && key === lastSyncKey && now - lastSyncAt < MIN_FULL_SYNC_MS) {
    return Promise.resolve({ skipped: true })
  }

  fullSyncPromise = (async () => {
    try {
      const result = await syncAllOfflineData(organizationId, branchId, { branches })
      if (organization?.id) {
        const { setMeta, normalizeOrgId, toPlainJson } = await import('./db')
        const oid = normalizeOrgId(organization.id)
        await setMeta(`organization_${oid}`, toPlainJson(organization))
        if (branches?.length) await setMeta(`branches_${oid}`, toPlainJson(branches))
      }
      lastSyncKey = key
      lastSyncAt = Date.now()
      dispatchSyncComplete(result)
      return result
    } finally {
      fullSyncPromise = null
    }
  })()

  return fullSyncPromise
}

export function schedulePendingSalesSync() {
  return runPendingOfflineSync()
}
