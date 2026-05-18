import { localDateTimeIso } from '../lib/localDateTime'
import { sales as salesApi } from '../services/sales.service'
import { ensurePendingDisplayNumbers, ensurePendingSaleDisplayFields } from './offlineSales'
import { getMeta, normalizeOrgId, savdoDb, setMeta, toPlainJson } from './db'

function saleTotalFromPayload(payload) {
  const items = payload?.items || []
  const subtotal = items.reduce((s, line) => {
    const qty = Number(line.quantity || 0)
    const price = Number(line.unit_price || 0)
    return s + qty * price
  }, 0)
  const discount = Number(payload?.discount || 0)
  return Math.max(0, subtotal - discount)
}

export function pendingSaleToRow(record) {
  const p = record.payload || {}
  return {
    id: record.display_no ?? record.server_id ?? '—',
    sold_at: p.sold_at || localDateTimeIso(new Date(record.created_at)),
    branch: p.branch,
    branch_name: record.branch_name || p.branch_name || '—',
    cashier_name: record.cashier_name || p.cashier_name || '—',
    debtor_name: record.debtor_name || null,
    status: 'pending',
    total: saleTotalFromPayload(p),
    _offlinePending: true,
    _client_uuid: record.client_uuid,
    items: (record.display_items || []).map((line, idx) => ({
      id: `p-${idx}`,
      product_name: line.product_name || `Mahsulot #${line.product}`,
      quantity: line.quantity,
      unit_price: line.unit_price,
      line_total: Number(line.quantity || 0) * Number(line.unit_price || 0),
    })),
  }
}

export async function syncSalesToIndexedDB(organizationId) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return false

  const list = await salesApi.list()
  if (!Array.isArray(list)) return false

  await setMeta(
    `sales_${orgId}`,
    list.map((s) => toPlainJson(s))
  )
  return true
}

export async function loadSalesFromIndexedDB(organizationId, { branchId } = {}) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return []

  const cached = (await getMeta(`sales_${orgId}`)) || []
  let rows = Array.isArray(cached) ? [...cached] : []

  if (branchId) {
    const bid = normalizeOrgId(branchId)
    rows = rows.filter((r) => !r.branch || Number(r.branch) === bid)
  }

  await ensurePendingDisplayNumbers(orgId)
  await ensurePendingSaleDisplayFields(orgId)

  const pending = await savdoDb.local_sales.where('status').equals('pending').toArray()
  const pendingRows = pending.map(pendingSaleToRow)

  const seen = new Set(rows.map((r) => String(r.id)))
  for (const pr of pendingRows) {
    if (!seen.has(String(pr.id))) rows.unshift(pr)
  }

  rows.sort((a, b) => new Date(b.sold_at || 0) - new Date(a.sold_at || 0))
  return rows
}
