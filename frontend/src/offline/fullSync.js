import api from '../services/api'
import { debtors as debtorsApi } from '../services/debtors.service'
import { normalizeOrgId, savdoDb, setMeta, toPlainJson } from './db'
import { syncCatalogToIndexedDB } from './catalogSync'
import { syncOfflineDebtors } from './offlineDebtors'
import { syncOfflineMutations } from './offlineMutations'
import { syncOfflineSales } from './offlineSales'
import { syncSalesToIndexedDB } from './salesCache'

export async function syncDebtorsToIndexedDB(organizationId) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return false

  const list = await debtorsApi.list()
  const active = (list || []).filter((d) => d.is_active !== false)

  await savdoDb.transaction('rw', savdoDb.debtors, async () => {
    await savdoDb.debtors.where('organizationId').equals(orgId).delete()
    if (active.length) {
      await savdoDb.debtors.bulkPut(
        active.map((d) => toPlainJson({ ...d, organizationId: orgId }))
      )
    }
  })

  return true
}

export async function syncBranchesMeta(organizationId, branches) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return
  await setMeta(`branches_${orgId}`, branches || [])
}

/** Internet/server ishlayotganda barcha POS ma'lumotlarini lokalga yozish. */
export async function syncAllOfflineData(organizationId, branchId, { branches } = {}) {
  const orgId = normalizeOrgId(organizationId)
  const bid = normalizeOrgId(branchId)
  if (!orgId || !bid) return { ok: false, reason: 'missing_context' }

  await syncOfflineMutations()
  await syncOfflineDebtors().catch(() => {})
  const catalogOk = await syncCatalogToIndexedDB(orgId, bid)
  await syncDebtorsToIndexedDB(orgId).catch(() => {})
  await syncSalesToIndexedDB(orgId).catch(() => {})

  if (branches?.length) {
    await syncBranchesMeta(orgId, branches)
  } else {
    try {
      const { data } = await api.get('/branches/')
      const list = data.results || data
      await syncBranchesMeta(orgId, list)
    } catch {
      /* ixtiyoriy */
    }
  }

  const salesResult = await syncOfflineSales().catch(() => ({ synced: 0, failed: 0 }))

  await setMeta('last_full_sync', {
    organizationId: orgId,
    branchId: bid,
    at: Date.now(),
  })

  return { ok: catalogOk !== false, sales: salesResult }
}

export async function loadDebtorsFromIndexedDB(organizationId) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return []
  const rows = await savdoDb.debtors.where('organizationId').equals(orgId).toArray()
  return rows.filter((d) => d.is_active !== false)
}
