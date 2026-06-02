import { stockMovements } from '../services/inventory.service'
import { checkApiReachable, isOfflineMode } from './connectivity'
import { normalizeOrgId, savdoDb, toPlainJson } from './db'
import { remapProductId, syncOfflineMutations } from './offlineMutations'
import { newClientUuid } from './offlineSales'

async function applyLocalStockReceipt(branchId, productId, quantity) {
  const bid = Number(branchId)
  const pid = Number(productId)
  const q = Number(quantity || 0)
  if (!bid || !pid || q <= 0) return

  const existing = await savdoDb.stockLevels.get({ branchId: bid, productId: pid })
  if (existing) {
    existing.quantity = Number(existing.quantity || 0) + q
    existing.is_low = Number(existing.quantity || 0) <= Number(existing.min_stock || 0)
    await savdoDb.stockLevels.put(existing)
    return
  }

  await savdoDb.stockLevels.put({
    branchId: bid,
    productId: pid,
    quantity: q,
    min_stock: 0,
    is_low: false,
  })
}

export async function saveOfflineStockReceipt(organizationId, payload) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) throw new Error('Tashkilot aniqlanmadi')

  const branchId = Number(payload.branch)
  const productId = Number(payload.product)
  const quantity = Number(payload.quantity || 0)
  if (!branchId || !productId || quantity <= 0) {
    throw new Error('Kirim maʼlumotlari noto‘g‘ri')
  }

  const row = toPlainJson({
    client_uuid: payload.client_uuid || newClientUuid(),
    status: 'pending',
    organizationId: orgId,
    branchId,
    productId,
    payload: {
      branch: branchId,
      product: productId,
      movement_type: 'in',
      quantity: String(payload.quantity),
      unit_cost: payload.unit_cost ?? 0,
      note: payload.note || '',
    },
    created_at: Date.now(),
  })

  await savdoDb.local_stock_receipts.put(row)
  await applyLocalStockReceipt(branchId, productId, quantity)
  return row
}

export async function countPendingStockReceipts() {
  return savdoDb.local_stock_receipts.where('status').equals('pending').count()
}

export async function getPendingStockReceiptMap(branchId = null) {
  const pending = await savdoDb.local_stock_receipts.where('status').equals('pending').toArray()
  const map = {}
  for (const row of pending) {
    if (branchId && Number(row.branchId) !== Number(branchId)) continue
    const pid = Number(row.productId)
    if (!pid) continue
    map[pid] = (map[pid] || 0) + 1
  }
  return map
}

export async function syncOfflineStockReceipts() {
  if (isOfflineMode()) {
    const ok = await checkApiReachable()
    if (!ok) return { synced: 0, failed: 0, skipped: true }
  }

  await syncOfflineMutations()

  const pending = await savdoDb.local_stock_receipts.where('status').equals('pending').toArray()
  pending.sort((a, b) => (a.created_at || 0) - (b.created_at || 0))

  let synced = 0
  let failed = 0

  for (const row of pending) {
    try {
      const mappedProduct = await remapProductId(row.productId)
      await stockMovements.create({
        ...row.payload,
        product: mappedProduct,
        movement_type: 'in',
        client_uuid: row.client_uuid,
      })
      await savdoDb.local_stock_receipts.update(row.client_uuid, {
        status: 'synced',
        synced_at: Date.now(),
      })
      synced += 1
    } catch (err) {
      console.warn('[offline] kirim sinxron:', row.client_uuid, err?.response?.data || err?.message)
      failed += 1
      if (!err?.response) break
    }
  }

  return { synced, failed }
}
