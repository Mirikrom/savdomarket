import { categories, products as productsApi } from '../services/catalog.service'
import { stockLevels } from '../services/inventory.service'
import { getMeta, normalizeOrgId, savdoDb, setMeta, toPlainJson } from './db'
import { isOfflineMode } from './connectivity'
import {
  dedupeCatalogProductRows,
  dedupeServerCatalogProducts,
  getPendingCatalogGuardIds,
  getProductIdMap,
  isPendingCatalogCategory,
  isPendingCatalogProduct,
  pruneStaleOfflineCatalog,
} from './offlineMutations'
import { sortProductsForDisplay } from '../lib/productSort'
import {
  attachCachedImagesToProducts,
  cacheProductImages,
  pruneOrphanedImages,
} from './imageCache'

function catalogMetaKey(orgId) {
  return `catalog_products_${orgId}`
}

function categoryMetaKey(orgId) {
  return `catalog_categories_${orgId}`
}

function productMatchesOrg(product, orgId) {
  if (Number(product.organizationId) === orgId) return true
  const org = product.organization
  if (Number(org) === orgId) return true
  if (org && typeof org === 'object' && Number(org.id) === orgId) return true
  return false
}

function filterActiveProducts(rows) {
  return rows.filter((p) => p.is_active !== false && !p.deleted_at)
}

/** Serverdan olingan ro‘yxatni IndexedDB ga yozish (qayta fetch shart emas). */
export async function persistCatalogToIndexedDB(organizationId, branchId, pList, cList, stockData) {
  const orgId = normalizeOrgId(organizationId)
  const bid = normalizeOrgId(branchId)
  if (!orgId || !bid) return false

  if (!Array.isArray(pList)) {
    throw new Error('Mahsulotlar ro‘yxati noto‘g‘ri javob qaytardi')
  }

  const stockRows = stockData?.results || stockData || []
  const now = Date.now()
  const idMap = await getProductIdMap()
  const activeProducts = dedupeServerCatalogProducts(filterActiveProducts(pList), idMap)

  const productRows = activeProducts.map((p) =>
    toPlainJson({
      ...p,
      organizationId: orgId,
      organization: orgId,
    })
  )

  if (activeProducts.length === 0) {
    await savdoDb.transaction('rw', savdoDb.products, savdoDb.meta, async () => {
      const existing = await savdoDb.products.where('organizationId').equals(orgId).toArray()
      for (const row of existing) {
        if (!productMatchesOrg(row, orgId)) continue
        await savdoDb.products.delete(row.id)
      }
      await setMeta(catalogMetaKey(orgId), [])
    })
    return true
  }
  const categoryRows = (cList || []).map((c) => toPlainJson({ ...c, organizationId: orgId }))
  const newIds = new Set(activeProducts.map((p) => p.id))
  const guard = await getPendingCatalogGuardIds()

  await savdoDb.transaction('rw', savdoDb.products, savdoDb.categories, savdoDb.stockLevels, savdoDb.meta, async () => {
    await savdoDb.products.bulkPut(productRows)

    const existing = await savdoDb.products.where('organizationId').equals(orgId).toArray()
    for (const row of existing) {
      if (!productMatchesOrg(row, orgId) || newIds.has(row.id)) continue
      if (isPendingCatalogProduct(row, guard)) continue
      await savdoDb.products.delete(row.id)
    }

    if (categoryRows.length) {
      await savdoDb.categories.bulkPut(categoryRows)
    }
    const newCatIds = new Set(categoryRows.map((c) => c.id))
    const existingCats = await savdoDb.categories.where('organizationId').equals(orgId).toArray()
    for (const row of existingCats) {
      if (newCatIds.has(row.id)) continue
      if (isPendingCatalogCategory(row, guard)) continue
      await savdoDb.categories.delete(row.id)
    }

    await savdoDb.stockLevels.where('branchId').equals(bid).delete()
    if (stockRows.length) {
      await savdoDb.stockLevels.bulkPut(
        stockRows.map((row) => ({
          branchId: bid,
          productId: row.product,
          quantity: Number(row.quantity || 0),
          updated_at: now,
        }))
      )
    }

    await savdoDb.meta.put({
      key: 'catalog_sync',
      value: toPlainJson({
        organizationId: orgId,
        branchId: bid,
        at: now,
        productCount: activeProducts.length,
      }),
    })
  })

  const pendingProducts = (
    await savdoDb.products.where('organizationId').equals(orgId).toArray()
  ).filter((p) => productMatchesOrg(p, orgId) && isPendingCatalogProduct(p, guard))
  const pendingCategories = (
    await savdoDb.categories.where('organizationId').equals(orgId).toArray()
  ).filter((c) => isPendingCatalogCategory(c, guard))
  const metaProducts = [
    ...productRows,
    ...pendingProducts.filter((p) => !newIds.has(p.id)),
  ]
  const metaCategories = [
    ...categoryRows,
    ...pendingCategories.filter((c) => !new Set(categoryRows.map((x) => x.id)).has(c.id)),
  ]
  await setMeta(catalogMetaKey(orgId), metaProducts)
  await setMeta(categoryMetaKey(orgId), metaCategories)
  await pruneStaleOfflineCatalog(orgId)

  localStorage.setItem('organization_id', String(orgId))
  localStorage.setItem('current_branch_id', String(bid))

  const productIds = activeProducts.map((p) => p.id)
  cacheProductImages(activeProducts, { concurrency: 2 }).catch(() => {})
  pruneOrphanedImages(productIds).catch(() => {})

  return true
}

export async function syncCatalogToIndexedDB(organizationId, branchId) {
  if (isOfflineMode()) return false

  const orgId = normalizeOrgId(organizationId)
  const bid = normalizeOrgId(branchId)
  if (!orgId || !bid) return false

  const [pList, cList, stockData] = await Promise.all([
    productsApi.list(),
    categories.list(),
    stockLevels.list({ branch: bid }),
  ])

  return persistCatalogToIndexedDB(orgId, bid, pList, cList, stockData)
}

async function loadProductsFromMeta(orgId) {
  const rows = await getMeta(catalogMetaKey(orgId))
  if (!Array.isArray(rows) || !rows.length) return []
  const guard = await getPendingCatalogGuardIds()
  const filtered = rows.filter((p) => {
    const id = Number(p.id)
    if (Number.isFinite(id) && id < 0 && !guard.productTempIds.has(id)) return false
    return true
  })
  if (filtered.length) {
    await savdoDb.products.bulkPut(filtered).catch(() => {})
  }
  return filterActiveProducts(filtered)
}

async function loadCategoriesFromMeta(orgId) {
  const rows = await getMeta(categoryMetaKey(orgId))
  if (!Array.isArray(rows) || !rows.length) return []
  await savdoDb.categories.bulkPut(rows).catch(() => {})
  return rows
}

/** Boshqa do‘kon (tashkilot) keshini o‘chirish — yangi ro‘yxatdan o‘tishda eski mahsulotlar chiqmasin. */
export async function purgeOfflineCatalogOtherOrgs(keepOrganizationId) {
  const keepOrgId = normalizeOrgId(keepOrganizationId)
  if (!keepOrgId) return

  const [allProducts, allCategories] = await Promise.all([
    savdoDb.products.toArray(),
    savdoDb.categories.toArray(),
  ])

  const productIdsToDrop = allProducts
    .filter((p) => !productMatchesOrg(p, keepOrgId))
    .map((p) => p.id)
  const categoryIdsToDrop = allCategories
    .filter((c) => Number(c.organizationId) !== keepOrgId)
    .map((c) => c.id)

  if (productIdsToDrop.length) {
    await savdoDb.products.bulkDelete(productIdsToDrop)
  }
  if (categoryIdsToDrop.length) {
    await savdoDb.categories.bulkDelete(categoryIdsToDrop)
  }

  const catalog = await getMeta('catalog_sync')
  const metaOrg = normalizeOrgId(catalog?.organizationId)
  if (metaOrg && metaOrg !== keepOrgId) {
    await savdoDb.meta.delete('catalog_sync')
  }
}

export async function loadCatalogFromIndexedDB(
  organizationId,
  branchId,
  { refreshFromApi = false, skipPrune = false } = {},
) {
  const orgId = normalizeOrgId(organizationId)
  const bid = branchId != null ? normalizeOrgId(branchId) : null

  if (orgId && bid && refreshFromApi && !isOfflineMode()) {
    try {
      await syncCatalogToIndexedDB(orgId, bid)
    } catch (err) {
      console.warn('[catalog] serverdan yangilab bo‘lmadi:', err)
    }
  }

  if (orgId && !skipPrune) {
    await pruneStaleOfflineCatalog(orgId)
  }

  if (!orgId) {
    const catalog = await getMeta('catalog_sync')
    const fallbackOrg = normalizeOrgId(catalog?.organizationId)
    if (!fallbackOrg) {
      return { products: [], categories: [], stockMap: {}, hasCache: false, syncedAt: null }
    }
    return loadCatalogFromIndexedDB(fallbackOrg, catalog?.branchId ?? bid)
  }

  let products = filterActiveProducts(
    (await savdoDb.products.where('organizationId').equals(orgId).toArray()).filter((p) =>
      productMatchesOrg(p, orgId),
    ),
  )

  if (!products.length) {
    products = filterActiveProducts(
      (await savdoDb.products.toArray()).filter((p) => productMatchesOrg(p, orgId)),
    )
  }

  if (!products.length) {
    products = await loadProductsFromMeta(orgId)
  }

  const guard = await getPendingCatalogGuardIds()
  const idMap = await getProductIdMap()
  products = dedupeCatalogProductRows(products, guard, idMap)
  products = sortProductsForDisplay(products)

  let categoryRows = (await savdoDb.categories.where('organizationId').equals(orgId).toArray())
  if (!categoryRows.length) {
    categoryRows = (await savdoDb.categories.toArray()).filter((c) => Number(c.organizationId) === orgId)
  }
  if (!categoryRows.length) {
    categoryRows = await loadCategoriesFromMeta(orgId)
  }

  const stockMap = {}
  if (bid) {
    const stockRows = await savdoDb.stockLevels.where('branchId').equals(bid).toArray()
    for (const row of stockRows) {
      stockMap[row.productId] = Number(row.quantity || 0)
    }
  }

  const meta = await getMeta('catalog_sync')
  const hasCache = products.length > 0

  return {
    products,
    categories: categoryRows,
    stockMap,
    hasCache,
    syncedAt: meta?.at || null,
  }
}

/** Faqat filial qoldig‘i — mahsulot ro‘yxatini almashtirmaydi (API dan yangi ro‘yxat saqlanadi). */
export async function loadStockMapFromIndexedDB(branchId) {
  const bid = normalizeOrgId(branchId)
  if (!bid) return {}

  const stockMap = {}
  const stockRows = await savdoDb.stockLevels.where('branchId').equals(bid).toArray()
  for (const row of stockRows) {
    stockMap[row.productId] = Number(row.quantity || 0)
  }
  return stockMap
}

export async function applyLocalStockDeduction(branchId, items) {
  const bid = normalizeOrgId(branchId)
  if (!bid) return

  await savdoDb.transaction('rw', savdoDb.stockLevels, async () => {
    for (const item of items) {
      const productId = item.product
      const row = await savdoDb.stockLevels.get({ branchId: bid, productId })
      const qty = Number(item.quantity || 0)
      if (row) {
        row.quantity = Number(row.quantity || 0) - qty
        await savdoDb.stockLevels.put(row)
      } else {
        await savdoDb.stockLevels.put({
          branchId: bid,
          productId,
          quantity: -qty,
          updated_at: Date.now(),
        })
      }
    }
  })
}
