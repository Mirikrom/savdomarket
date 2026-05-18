import { localDateTimeIso } from '../lib/localDateTime'
import { sales } from '../services/sales.service'
import { checkApiReachable, isOfflineMode } from './connectivity'
import { applyLocalStockDeduction } from './catalogSync'
import { resolveDebtorServerId, syncOfflineDebtors } from './offlineDebtors'
import { remapProductId, syncOfflineMutations } from './offlineMutations'
import {
  getPersistedCashierName,
  persistCashierName,
  resolveOfflineCashierName,
} from './posContext'
import { getMeta, normalizeOrgId, savdoDb, setMeta, toPlainJson } from './db'

export function newClientUuid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/** Django API uchun toza payload (product_name va boshqalar olib tashlanadi). */
export function buildApiSalePayload(payload) {
  const items = (payload.items || []).map((line) => {
    const row = {
      product: Number(line.product),
      quantity: String(line.quantity),
      unit_price: String(line.unit_price),
    }
    if (line.batch != null && line.batch !== '') {
      row.batch = Number(line.batch)
    }
    return row
  })

  const payments = (payload.payments || []).map((p) => ({
    method: p.method,
    amount: String(p.amount),
    ...(p.transaction_ref ? { transaction_ref: p.transaction_ref } : {}),
  }))

  return {
    client_uuid: payload.client_uuid,
    sold_at: payload.sold_at,
    allow_offline: true,
    branch: Number(payload.branch),
    discount: payload.discount ?? 0,
    note: payload.note || '',
    items,
    payments,
    ...(payload.debtor && Number(payload.debtor) > 0 ? { debtor: Number(payload.debtor) } : {}),
  }
}

function resolveSoldAt(payload, recordCreatedAt) {
  if (payload?.sold_at) return payload.sold_at
  if (recordCreatedAt) return localDateTimeIso(new Date(recordCreatedAt))
  return localDateTimeIso()
}

/** Keshdagi oxirgi chek raqamidan keyingi ketma-ket raqam (15, 16, …). */
export async function computeMaxReceiptNumber(organizationId) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return 0

  const cached = (await getMeta(`sales_${orgId}`)) || []
  let maxId = 0
  for (const sale of cached) {
    const n = Number(sale.id)
    if (Number.isFinite(n) && n > maxId) maxId = n
  }

  const localRows = await savdoDb.local_sales.toArray()
  for (const row of localRows) {
    for (const key of [row.display_no, row.server_id]) {
      const n = Number(key)
      if (Number.isFinite(n) && n > maxId) maxId = n
    }
  }

  return maxId
}

export async function getNextOfflineReceiptNumber(organizationId) {
  return (await computeMaxReceiptNumber(organizationId)) + 1
}

/** Eski offline yozuvlarga filial va kassir nomini qo‘shish. */
export async function ensurePendingSaleDisplayFields(organizationId) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return

  const branches = (await getMeta(`branches_${orgId}`)) || []
  const cashier = (await getMeta('cashier_snapshot')) || null
  const pending = await savdoDb.local_sales.where('status').equals('pending').toArray()

  for (const row of pending) {
    const p = row.payload || {}
    const updates = {}

    if (!row.branch_name && p.branch) {
      const branch = branches.find((b) => Number(b.id) === Number(p.branch))
      if (branch?.name) updates.branch_name = branch.name
    }
    if (!row.cashier_name) {
      const name =
        cashier?.full_name ||
        cashier?.name ||
        cashier?.username ||
        getPersistedCashierName()
      if (name) updates.cashier_name = name
    }

    if (Object.keys(updates).length) {
      await savdoDb.local_sales.update(row.client_uuid, updates)
      Object.assign(row, updates)
    }
  }
}

/** Eski offline yozuvlarga ham ketma-ket chek raqami berish. */
export async function ensurePendingDisplayNumbers(organizationId) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return

  const pending = await savdoDb.local_sales.where('status').equals('pending').toArray()
  pending.sort((a, b) => (a.created_at || 0) - (b.created_at || 0))

  let next = (await computeMaxReceiptNumber(orgId)) + 1
  for (const row of pending) {
    if (row.display_no) continue
    await savdoDb.local_sales.update(row.client_uuid, { display_no: next })
    row.display_no = next
    next += 1
  }
}

export async function saveOfflineSale(payload) {
  const client_uuid = payload.client_uuid || newClientUuid()
  const sold_at = resolveSoldAt(payload)
  const orgId = normalizeOrgId(
    payload.organization_id ?? localStorage.getItem('organization_id')
  )
  const display_no = await getNextOfflineReceiptNumber(orgId)

  const displayItems = payload.items || []
  const cashier_name = await resolveOfflineCashierName(null, payload.cashier_name)
  if (cashier_name) {
    persistCashierName(cashier_name)
    await setMeta(
      'cashier_snapshot',
      toPlainJson({
        full_name: cashier_name,
        name: cashier_name,
      })
    )
  }

  const record = {
    client_uuid,
    status: 'pending',
    created_at: Date.now(),
    sold_at,
    display_no,
    branch_name: payload.branch_name || '',
    cashier_name,
    debtor_name: payload.debtor_name || '',
    debtor_client_uuid: payload.debtor_client_uuid || null,
    display_items: displayItems,
    payload: buildApiSalePayload({
      ...payload,
      client_uuid,
      sold_at,
      debtor: payload.debtor && Number(payload.debtor) > 0 ? payload.debtor : undefined,
    }),
  }

  await savdoDb.local_sales.put(toPlainJson(record))
  await applyLocalStockDeduction(payload.branch, payload.items)
  return buildOfflineReceipt(record)
}

function buildOfflineReceipt(record) {
  const p = record.payload
  const soldAt = record.sold_at || p.sold_at
  const sourceItems = record.display_items || p.items || []
  const items = sourceItems.map((line, idx) => {
    const qty = Number(line.quantity || 0)
    const price = Number(line.unit_price || 0)
    return {
      id: `offline-${record.client_uuid}-${idx}`,
      product: line.product,
      product_name: line.product_name || `Mahsulot #${line.product}`,
      quantity: line.quantity,
      unit_price: line.unit_price,
      line_total: (qty * price).toFixed(2),
    }
  })
  const subtotal = items.reduce((s, i) => s + Number(i.line_total || 0), 0)
  const discount = Number(p.discount || 0)
  const total = Math.max(0, subtotal - discount)
  const paid = (p.payments || []).reduce((s, pay) => s + Number(pay.amount || 0), 0)
  return {
    id: record.display_no,
    client_uuid: record.client_uuid,
    sold_at: soldAt,
    debtor_name: record.debtor_name || '',
    subtotal,
    discount,
    total,
    paid,
    change: Math.max(0, paid - total),
    items,
    offline: true,
  }
}

export async function countPendingSales() {
  return savdoDb.local_sales.where('status').equals('pending').count()
}

export async function syncOfflineSales() {
  if (isOfflineMode()) {
    const ok = await checkApiReachable()
    if (!ok) return { synced: 0, failed: 0, skipped: true }
  }

  await syncOfflineMutations()
  await syncOfflineDebtors()

  const pending = await savdoDb.local_sales.where('status').equals('pending').toArray()
  pending.sort((a, b) => (a.created_at || 0) - (b.created_at || 0))

  let synced = 0
  let failed = 0

  for (const row of pending) {
    try {
      const soldAt = resolveSoldAt(row.payload, row.created_at || row.sold_at)
      const apiPayload = {
        ...row.payload,
        sold_at: soldAt,
        allow_offline: true,
      }

      const debtorId = await resolveDebtorServerId(
        apiPayload.debtor,
        row.debtor_client_uuid
      )
      if (debtorId) apiPayload.debtor = debtorId
      else delete apiPayload.debtor

      if (Array.isArray(apiPayload.items)) {
        for (const item of apiPayload.items) {
          const mapped = await remapProductId(item.product)
          item.product = mapped
        }
      }

      const result = await sales.create(apiPayload)
      await savdoDb.local_sales.update(row.client_uuid, {
        status: 'synced',
        server_id: result.id,
        synced_at: Date.now(),
      })
      synced += 1
    } catch (err) {
      console.warn('[offline] savdo sinxron xato:', row.client_uuid, err?.response?.data || err?.message)
      failed += 1
      if (!err?.response) break
    }
  }

  return { synced, failed }
}
