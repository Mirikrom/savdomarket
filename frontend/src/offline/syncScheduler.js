import { isOfflineMode } from './connectivity'
import { syncAllOfflineData } from './fullSync'
import { syncOfflineSales } from './offlineSales'

const MIN_FULL_SYNC_MS = 3 * 60 * 1000

let fullSyncPromise = null
let lastSyncKey = ''
let lastSyncAt = 0

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
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('savdopro:sync-complete'))
      }
      return result
    } finally {
      fullSyncPromise = null
    }
  })()

  return fullSyncPromise
}

export function schedulePendingSalesSync() {
  return syncOfflineSales().catch(() => ({ synced: 0, failed: 0 }))
}
