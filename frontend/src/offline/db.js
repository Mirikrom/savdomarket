import Dexie from 'dexie'

export const savdoDb = new Dexie('SavdoProOffline')

savdoDb.version(1).stores({
  meta: 'key',
  products: 'id, organizationId, category, barcode, sku, name, is_active',
  categories: 'id, organizationId',
  stockLevels: '[branchId+productId], branchId, productId',
  local_sales: 'client_uuid, status, created_at',
})

savdoDb.version(2).stores({
  product_images: 'productId',
})

savdoDb.version(3).stores({
  debtors: 'id, organizationId, name, is_active',
})

savdoDb.version(4).stores({
  local_debtors: 'client_uuid, status, organizationId, created_at',
  local_mutations: 'client_uuid, kind, status, created_at',
})

savdoDb.version(5).stores({
  local_debt_payments: 'client_uuid, status, organizationId, debtor_ref, created_at',
})

savdoDb.version(6).stores({
  local_stock_receipts: 'client_uuid, status, organizationId, branchId, productId, created_at',
})

/** Vue/Pinia Proxy va boshqa narsalarni IndexedDB uchun xavfsiz JSON ga aylantiradi. */
export function toPlainJson(value) {
  if (value === undefined) return null
  return JSON.parse(JSON.stringify(value))
}

export async function setMeta(key, value) {
  await savdoDb.meta.put({ key, value: toPlainJson(value) })
}

export async function getMeta(key) {
  const row = await savdoDb.meta.get(key)
  return row?.value ?? null
}

export function normalizeOrgId(id) {
  const n = Number(id)
  return Number.isFinite(n) ? n : null
}
