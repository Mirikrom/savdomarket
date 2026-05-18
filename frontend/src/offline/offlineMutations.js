import { categories, products as productsApi } from '../services/catalog.service'
import { isOfflineMode } from './connectivity'
import { getMeta, normalizeOrgId, savdoDb, setMeta, toPlainJson } from './db'
import { localDateTimeIso } from '../lib/localDateTime'
import { newClientUuid } from './offlineSales'

const PRODUCT_ID_MAP_KEY = 'offline_product_id_map'
const CATEGORY_ID_MAP_KEY = 'offline_category_id_map'

async function getCategoryIdMap() {
  return (await getMeta(CATEGORY_ID_MAP_KEY)) || {}
}

async function setCategoryIdMap(map) {
  await setMeta(CATEGORY_ID_MAP_KEY, map)
}

function resolveCategoryId(category, catMap) {
  if (category == null || category === '') return null
  const n = Number(category)
  if (Number.isFinite(n) && n < 0) {
    const mapped = catMap[String(n)]
    return mapped != null ? Number(mapped) : null
  }
  return category
}

/** Katalog sync offline yozuvlarni o‘chirmasligi uchun. */
/** Mahsulot jadvali: qaysi ID lar sinxron kutmoqda. */
export async function getPendingProductSyncMap() {
  const pending = await savdoDb.local_mutations.where('status').equals('pending').toArray()
  const pendingCreateIds = new Set()
  const pendingUpdateIds = new Set()

  for (const row of pending) {
    const p = row.payload || {}
    if (row.kind === 'product_create' && p.tempId != null) {
      pendingCreateIds.add(Number(p.tempId))
    }
    if (row.kind === 'product_update' && p.productId != null) {
      pendingUpdateIds.add(Number(p.productId))
    }
  }

  return { pendingCreateIds, pendingUpdateIds }
}

export function resolveProductSyncStatus(row, { pendingCreateIds, pendingUpdateIds }) {
  const id = Number(row?.id)
  if (
    row?._offlinePending ||
    pendingCreateIds?.has(id) ||
    (Number.isFinite(id) && id < 0 && pendingCreateIds?.has(id))
  ) {
    return 'pending'
  }
  if (pendingUpdateIds?.has(id)) {
    return 'pending_update'
  }
  return 'synced'
}

export async function getPendingCatalogGuardIds() {
  const pending = await savdoDb.local_mutations.where('status').equals('pending').toArray()
  const productTempIds = new Set()
  const categoryTempIds = new Set()

  for (const row of pending) {
    const p = row.payload || {}
    if (row.kind === 'product_create' && p.tempId != null) {
      productTempIds.add(Number(p.tempId))
    }
    if (row.kind === 'category_create' && p.tempId != null) {
      categoryTempIds.add(Number(p.tempId))
    }
    if (row.kind === 'product_update' && p.productId != null) {
      const pid = Number(p.productId)
      if (Number.isFinite(pid) && pid < 0) productTempIds.add(pid)
    }
  }

  return { productTempIds, categoryTempIds }
}

export function isPendingCatalogProduct(row, guard) {
  if (!row) return false
  const id = Number(row.id)
  return guard?.productTempIds?.has(id) ?? false
}

export function isPendingCatalogCategory(row, guard) {
  if (!row) return false
  const id = Number(row.id)
  return guard?.categoryTempIds?.has(id) ?? false
}

function productMatchesOrg(product, orgId) {
  if (Number(product.organizationId) === orgId) return true
  const org = product.organization
  if (Number(org) === orgId) return true
  if (org && typeof org === 'object' && Number(org.id) === orgId) return true
  return false
}

async function deleteLocalProductById(productId) {
  const id = Number(productId)
  if (!Number.isFinite(id)) return
  await savdoDb.products.delete(id).catch(() => {})
  const stockRows = await savdoDb.stockLevels.where('productId').equals(id).toArray()
  for (const s of stockRows) {
    await savdoDb.stockLevels.delete({ branchId: s.branchId, productId: id }).catch(() => {})
  }
}

/** Ro‘yxatda dublikat: serverdagi + eski vaqtincha yozuv. */
export function dedupeCatalogProductRows(products, guard, idMap = {}) {
  const positiveNameKeys = new Set(
    products
      .filter((p) => Number(p.id) > 0)
      .map((p) => (p.name || '').trim().toLowerCase())
      .filter(Boolean)
  )

  return products.filter((p) => {
    const id = Number(p.id)
    if (!Number.isFinite(id) || id >= 0) return true
    if (guard?.productTempIds?.has(id)) return true
    if (idMap[String(id)]) return false
    const nameKey = (p.name || '').trim().toLowerCase()
    if (nameKey && positiveNameKeys.has(nameKey)) return false
    return false
  })
}

/** Serverdan o‘chganda yoki qo‘lda: mahsulot + vaqtincha nusxalarini keshdan olib tashlash. */
export async function purgeProductFromLocalCache(organizationId, productId) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return

  const idMap = await getProductIdMap()
  const idsToDelete = new Set()
  const pid = Number(productId)

  if (Number.isFinite(pid)) idsToDelete.add(pid)
  for (const [tempKey, serverId] of Object.entries(idMap)) {
    if (Number(serverId) === pid) idsToDelete.add(Number(tempKey))
    if (pid === Number(tempKey)) idsToDelete.add(Number(tempKey))
  }

  for (const id of idsToDelete) {
    await deleteLocalProductById(id)
  }

  const pending = await savdoDb.local_mutations.where('status').equals('pending').toArray()
  for (const m of pending) {
    const tempId = Number(m.payload?.tempId)
    if (m.kind === 'product_create' && idsToDelete.has(tempId)) {
      await savdoDb.local_mutations.delete(m.client_uuid).catch(() => {})
    }
  }

  const nextMap = { ...idMap }
  for (const id of idsToDelete) {
    delete nextMap[String(id)]
  }
  for (const [k, v] of Object.entries({ ...nextMap })) {
    if (idsToDelete.has(Number(v))) delete nextMap[k]
  }
  await setProductIdMap(nextMap)

  const metaKey = `catalog_products_${orgId}`
  const metaRows = await getMeta(metaKey)
  if (Array.isArray(metaRows)) {
    await setMeta(
      metaKey,
      metaRows.filter((p) => !idsToDelete.has(Number(p.id)))
    )
  }

  await pruneStaleOfflineCatalog(orgId)
}

/** Sinxronlangan, lekin keshda qolgan vaqtincha (manfiy ID) yozuvlarni tozalash. */
export async function pruneStaleOfflineCatalog(organizationId) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return

  const guard = await getPendingCatalogGuardIds()
  const idMap = await getProductIdMap()

  const products = await savdoDb.products.toArray()
  for (const row of products) {
    if (!productMatchesOrg(row, orgId)) continue
    const id = Number(row.id)
    if (!Number.isFinite(id) || id >= 0) continue
    if (guard.productTempIds.has(id)) continue
    if (idMap[String(id)]) {
      await deleteLocalProductById(id)
      continue
    }

    await deleteLocalProductById(id)
  }

  const categories = await savdoDb.categories.toArray()
  for (const row of categories) {
    if (Number(row.organizationId) !== orgId) continue
    const id = Number(row.id)
    if (!Number.isFinite(id) || id >= 0) continue
    if (guard.categoryTempIds.has(id)) continue
    await savdoDb.categories.delete(id)
  }

  const metaKey = `catalog_products_${orgId}`
  const metaRows = await getMeta(metaKey)
  if (Array.isArray(metaRows) && metaRows.length) {
    const cleaned = metaRows.filter((p) => {
      const id = Number(p.id)
      if (Number.isFinite(id) && id < 0 && !guard.productTempIds.has(id)) return false
      return true
    })
    if (cleaned.length !== metaRows.length) {
      await setMeta(metaKey, cleaned)
    }
  }

  const catMetaKey = `catalog_categories_${orgId}`
  const catMetaRows = await getMeta(catMetaKey)
  if (Array.isArray(catMetaRows) && catMetaRows.length) {
    const cleaned = catMetaRows.filter((c) => {
      const id = Number(c.id)
      if (Number.isFinite(id) && id < 0 && !guard.categoryTempIds.has(id)) return false
      return true
    })
    if (cleaned.length !== catMetaRows.length) {
      await setMeta(catMetaKey, cleaned)
    }
  }
}

export function nextOfflineProductId() {
  return -Math.floor(Date.now() + Math.random() * 1000)
}

export async function getProductIdMap() {
  return (await getMeta(PRODUCT_ID_MAP_KEY)) || {}
}

async function setProductIdMap(map) {
  await setMeta(PRODUCT_ID_MAP_KEY, map)
}

export async function remapProductId(productId) {
  const n = Number(productId)
  if (Number.isFinite(n) && n > 0) return n
  const map = await getProductIdMap()
  return map[String(productId)] ? Number(map[String(productId)]) : n
}

async function resolveBranchIdForProduct(payload) {
  let bid = normalizeOrgId(payload?.branch)
  if (bid) return bid
  const catalog = await getMeta('catalog_sync')
  bid = normalizeOrgId(catalog?.branchId)
  if (bid) return bid
  if (typeof localStorage !== 'undefined') {
    return normalizeOrgId(localStorage.getItem('current_branch_id'))
  }
  return null
}

export async function upsertLocalStockLevel(branchId, productId, quantity) {
  const bid = normalizeOrgId(branchId)
  const pid = Number(productId)
  if (!bid || !Number.isFinite(pid)) return

  await savdoDb.stockLevels.put({
    branchId: bid,
    productId: pid,
    quantity: Number(quantity || 0),
    updated_at: Date.now(),
  })
}

async function migrateLocalStockProductId(tempId, newProductId) {
  const fromId = Number(tempId)
  const toId = Number(newProductId)
  if (!Number.isFinite(fromId) || !Number.isFinite(toId) || fromId === toId) return

  const rows = await savdoDb.stockLevels.where('productId').equals(fromId).toArray()
  for (const row of rows) {
    await savdoDb.stockLevels.delete({ branchId: row.branchId, productId: fromId })
    await savdoDb.stockLevels.put({
      branchId: row.branchId,
      productId: toId,
      quantity: Number(row.quantity || 0),
      updated_at: Date.now(),
    })
  }
}

export async function queueMutation(kind, payload, organizationId) {
  const client_uuid = newClientUuid()
  await savdoDb.local_mutations.put(
    toPlainJson({
      client_uuid,
      kind,
      status: 'pending',
      organizationId: normalizeOrgId(organizationId),
      payload,
      created_at: Date.now(),
    })
  )
  return client_uuid
}

export async function offlineCreateProduct(organizationId, payload, { imageFile } = {}) {
  const orgId = normalizeOrgId(organizationId)
  const tempId = nextOfflineProductId()
  const row = toPlainJson({
    ...payload,
    id: tempId,
    organizationId: orgId,
    organization: orgId,
    is_active: true,
    image_url: '',
    created_at: localDateTimeIso(),
    _offlinePending: true,
  })

  await savdoDb.products.put(row)

  const branchId = await resolveBranchIdForProduct(payload)
  if (branchId) {
    await upsertLocalStockLevel(branchId, tempId, payload.initial_quantity ?? 0)
  }

  await queueMutation('product_create', { ...payload, tempId, hasImage: Boolean(imageFile) }, orgId)

  return row
}

export async function offlineUpdateProduct(productId, payload, { imageFile, clearImage } = {}) {
  const existing = await savdoDb.products.get(Number(productId))
  if (!existing) throw new Error('Mahsulot keshda topilmadi')

  const updated = toPlainJson({
    ...existing,
    ...payload,
    id: Number(productId),
    _offlinePending: true,
  })
  await savdoDb.products.put(updated)
  await queueMutation(
    'product_update',
    { productId: Number(productId), payload, clearImage: Boolean(clearImage), hasImage: Boolean(imageFile) },
    existing.organizationId
  )
  return updated
}

export async function offlineCreateCategory(organizationId, { name }) {
  const orgId = normalizeOrgId(organizationId)
  const tempId = -Math.floor(Date.now() + Math.random() * 500)
  const row = toPlainJson({
    id: tempId,
    organizationId: orgId,
    name: String(name || '').trim(),
    _offlinePending: true,
  })
  await savdoDb.categories.put(row)
  await queueMutation('category_create', { name: row.name, tempId }, orgId)
  return row
}

export async function syncOfflineMutations() {
  if (isOfflineMode()) return { synced: 0, failed: 0, skipped: true }

  const pending = await savdoDb.local_mutations.where('status').equals('pending').toArray()
  pending.sort((a, b) => (a.created_at || 0) - (b.created_at || 0))

  const idMap = await getProductIdMap()
  const catMap = await getCategoryIdMap()
  let synced = 0
  let failed = 0

  for (const row of pending) {
    try {
      const p = row.payload || {}
      if (row.kind === 'product_create') {
        if (p.tempId != null && idMap[String(p.tempId)]) {
          await deleteLocalProductById(p.tempId)
          await savdoDb.local_mutations.update(row.client_uuid, {
            status: 'synced',
            synced_at: Date.now(),
          })
          synced += 1
          continue
        }
        const created = await productsApi.create({
          name: p.name,
          category: resolveCategoryId(p.category, catMap),
          sku: p.sku || '',
          barcode: p.barcode || '',
          unit: p.unit || 'piece',
          sell_price: p.sell_price ?? 0,
          cost_price: p.cost_price ?? 0,
          min_stock: p.min_stock ?? 0,
          branch: p.branch || null,
          initial_quantity: p.initial_quantity ?? 0,
        })
        if (p.tempId != null) {
          idMap[String(p.tempId)] = created.id
          await migrateLocalStockProductId(p.tempId, created.id)
          await deleteLocalProductById(p.tempId)
          await savdoDb.products.put(
            toPlainJson({
              ...created,
              organizationId: row.organizationId,
              organization: row.organizationId,
            })
          )
        }
      } else if (row.kind === 'product_update') {
        let pid = Number(p.productId)
        if (pid < 0 && idMap[String(pid)]) pid = Number(idMap[String(pid)])
        const payload = { ...(p.payload || {}) }
        if (payload.category != null) {
          payload.category = resolveCategoryId(payload.category, catMap)
        }
        await productsApi.update(pid, payload)
      } else if (row.kind === 'category_create') {
        const created = await categories.create({ name: p.name })
        if (p.tempId != null) {
          catMap[String(p.tempId)] = created.id
          await savdoDb.categories.delete(Number(p.tempId))
          await savdoDb.categories.put(
            toPlainJson({ ...created, organizationId: row.organizationId })
          )
        }
      }

      await savdoDb.local_mutations.update(row.client_uuid, {
        status: 'synced',
        synced_at: Date.now(),
      })
      synced += 1
    } catch (err) {
      console.warn('[offline] mutation sinxron:', row.kind, err?.response?.data || err?.message)
      failed += 1
      if (!err?.response) break
    }
  }

  await setProductIdMap(idMap)
  await setCategoryIdMap(catMap)

  const orgIds = new Set(
    pending.map((r) => normalizeOrgId(r.organizationId)).filter(Boolean)
  )
  const catalog = await getMeta('catalog_sync')
  const catalogOrg = normalizeOrgId(catalog?.organizationId)
  if (catalogOrg) orgIds.add(catalogOrg)
  for (const oid of orgIds) {
    await pruneStaleOfflineCatalog(oid)
  }

  return { synced, failed }
}
