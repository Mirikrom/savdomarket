<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import AppModal from '../../components/AppModal.vue'
import BarcodeScanner from '../../components/BarcodeScanner.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import SyncStatusIcon from '../../components/SyncStatusIcon.vue'
import {
  compareProductsCreationOrder,
  sortProductsForDisplay,
} from '../../lib/productSort'
import { POS_SHELL_QUERY_KEY, POS_SHELL_QUERY_VALUE } from '../../posShellQuery'
import {
  loadCatalogFromIndexedDB,
  loadStockMapFromIndexedDB,
  persistCatalogToIndexedDB,
} from '../../offline/catalogSync'
import {
  attachCachedImagesToProducts,
  cacheProductImages,
  resolveProductImageSrc,
} from '../../offline/imageCache'
import {
  checkApiReachable,
  isOfflineMode,
  markApiReachable,
  onConnectivityChange,
} from '../../offline/connectivity'
import { hydrateOrganizationStore, resolvePosIds } from '../../offline/posContext'
import {
  dedupeCatalogProductRows,
  getPendingCatalogGuardIds,
  getPendingProductSyncMap,
  getProductIdMap,
  offlineCreateCategory,
  offlineCreateProduct,
  offlineUpdateProduct,
  pruneStaleOfflineCatalog,
  purgeProductFromLocalCache,
  resolveProductSyncStatus,
  syncOfflineMutations,
} from '../../offline/offlineMutations'
import { useApiNotify } from '../../composables/useApiNotify'
import { categories, products } from '../../services/catalog.service'
import { stockLevels } from '../../services/inventory.service'
import { collatorLocaleForUi, numberLocaleForUi, useI18n } from '../../i18n'
import { useAuthStore } from '../../stores/auth'
import { useOrganizationStore } from '../../stores/organization'
import { resolveApiError } from '../../utils/apiErrors'

const route = useRoute()
const auth = useAuthStore()
const { tr, locale, branchLabel } = useI18n()
const { showApiError, showMessage } = useApiNotify()
const org = useOrganizationStore()

/** Kassa (POS) mahsulotlar: tan narxi ko‘rinmasin; PATCH da ham yuborilmaydi. */
const hideCostInPos = computed(() => {
  const q = route.query[POS_SHELL_QUERY_KEY]
  if (q === POS_SHELL_QUERY_VALUE || q === 'true') return true
  return auth.isSeller
})

const rows = ref([])
const categoryList = ref([])
/** product_id → { quantity, is_low, min_stock } (joriy filial) */
const stockMap = ref({})
const search = ref('')
const filters = reactive({ syncStatus: '' })
const pendingSyncMap = ref({ pendingCreateIds: new Set(), pendingUpdateIds: new Set() })

function numberLocale() {
  return numberLocaleForUi(locale.value)
}

const syncStatusLabelMap = computed(() => ({
  synced: tr('page.products.sync.synced'),
  pending: tr('page.products.sync.pending'),
  pending_update: tr('page.products.sync.pending_update'),
}))

const syncStatusFilterOptions = computed(() =>
  ['synced', 'pending', 'pending_update'].map((code) => ({
    code,
    label: syncStatusLabelMap.value[code],
  })),
)

const unitOptions = computed(() => [
  { value: 'piece', label: tr('page.products.unit.piece') },
  { value: 'kg', label: tr('page.products.unit.kg') },
  { value: 'liter', label: tr('page.products.unit.liter') },
  { value: 'pack', label: tr('page.products.unit.pack') },
])

function productSyncIconKind(status) {
  if (status === 'synced') return 'synced'
  return 'pending'
}

const loading = ref(false)
/** Jadvalda ma’lumot bir marta chiqgach, qayta «Yuklanmoqda» ko‘rsatilmaydi. */
const hasDisplayedProducts = ref(false)
const isOnline = ref(!isOfflineMode())
const catalogOffline = ref(false)
const modalOpen = ref(false)
const editingId = ref(null)
const apiError = ref('')
const categoryQuickError = ref('')
const saving = ref(false)
const scannerOpen = ref(false)
const scanTarget = ref('barcode') // 'barcode' yoki 'search'
const showQuickCategory = ref(false)
const newCategoryName = ref('')
const categorySaving = ref(false)

const form = reactive({
  name: '',
  category: '',
  sku: '',
  barcode: '',
  unit: 'piece',
  sell_price: '0',
  cost_price: '0',
  min_stock: '0',
  quantity: '0',
  branch: '',
})

const productImageInput = ref(null)
const imageFile = ref(null)
const clearProductImage = ref(false)
const imagePreviewUrl = ref('')
const editingHadImage = ref(false)
let imagePreviewBlobUrl = null

function resolveMediaUrl(url) {
  if (!url) return ''
  if (/^https?:\/\//i.test(url) || url.startsWith('//')) return url
  if (url.startsWith('blob:')) return url
  return url.startsWith('/') ? url : `/${url}`
}

/** Kassa bilan bir xil — offline blob kesh, keyin server URL. */
function productRowImageSrc(row) {
  if (!row) return ''
  if (row._cachedImageUrl) return row._cachedImageUrl
  return resolveProductImageSrc(row)
}

function productRowHasImage(row) {
  return Boolean(productRowImageSrc(row))
}

/** Jadvalda rasm yo‘q bo‘lsa — qisqa initial */
function productRowInitials(row) {
  const n = (row?.name || '').trim()
  if (!n) return '?'
  const parts = n.split(/\s+/).filter(Boolean)
  if (parts.length >= 2)
    return (parts[0].charAt(0) + parts[1].charAt(0)).toUpperCase().slice(0, 2)
  return n.slice(0, 2).toUpperCase()
}

function revokeImageBlobPreview() {
  if (imagePreviewBlobUrl) {
    URL.revokeObjectURL(imagePreviewBlobUrl)
    imagePreviewBlobUrl = null
  }
}

function setImagePreviewFromFile(file) {
  revokeImageBlobPreview()
  if (!file) {
    imagePreviewUrl.value = ''
    return
  }
  imagePreviewBlobUrl = URL.createObjectURL(file)
  imagePreviewUrl.value = imagePreviewBlobUrl
}

const productColumnsBase = computed(() => {
  const loc = numberLocale()
  return [
    {
      key: '_displayNo',
      label: tr('page.products.colNo'),
      width: '56px',
    },
    {
      key: 'image_url',
      label: tr('page.products.colImage'),
      width: '84px',
    },
    { key: 'name', label: tr('page.products.colName') },
    {
      key: 'category',
      label: tr('page.products.colCategory'),
      formatter: (v) => categoryList.value.find((c) => c.id === v)?.name || '—',
      width: '160px',
    },
    { key: 'sku', label: 'SKU', width: '120px' },
    { key: 'barcode', label: tr('page.products.colBarcode'), width: '140px' },
    {
      key: 'unit',
      label: tr('page.products.colUnit'),
      formatter: (v) => unitOptions.value.find((u) => u.value === v)?.label || v,
      width: '90px',
    },
    {
      key: '_stockQty',
      label: tr('page.products.colStock'),
      width: '120px',
    },
    {
      key: '_syncStatus',
      label: tr('page.products.colStatus'),
      width: '72px',
    },
    {
      key: 'sell_price',
      label: tr('page.products.colPrice'),
      formatter: (v) => Number(v).toLocaleString(loc),
      width: '100px',
    },
    {
      key: 'cost_price',
      label: tr('page.products.colCost'),
      formatter: (v) => Number(v ?? 0).toLocaleString(loc),
      width: '100px',
    },
  ]
})

const columns = computed(() => {
  const base = productColumnsBase.value
  if (hideCostInPos.value) {
    return base.filter((c) => c.key !== 'cost_price')
  }
  return base
})

const filteredRows = computed(() => {
  let list = rows.value
  if (filters.syncStatus) {
    list = list.filter(
      (r) => resolveProductSyncStatus(r, pendingSyncMap.value) === filters.syncStatus
    )
  }
  const q = search.value.trim().toLowerCase()
  if (!q) return list
  return list.filter(
    (r) =>
      r.name?.toLowerCase().includes(q) ||
      r.sku?.toLowerCase().includes(q) ||
      r.barcode?.toLowerCase().includes(q),
  )
})

/** № ustuni: eng avval yaratilgan = 1 (server -id tartibiga mos kalit). */
const creationRankById = computed(() => {
  const sorted = [...rows.value].sort(compareProductsCreationOrder)
  const map = new Map()
  sorted.forEach((r, i) => {
    map.set(r.id, i + 1)
  })
  return map
})

const displayRows = computed(() =>
  sortProductsForDisplay(filteredRows.value).map((row) => {
    const stock = stockMap.value[row.id]
    return {
      ...row,
      _displayNo: creationRankById.value.get(row.id) ?? '—',
      _stockQty: stock?.quantity ?? 0,
      _stockLow: Boolean(stock?.is_low),
      _syncStatus: resolveProductSyncStatus(row, pendingSyncMap.value),
    }
  }),
)

/** Ma’lumot chiqgach jadval yana «Yuklanmoqda» bilan yashirilmaydi. */
const tableLoading = computed(() => loading.value && displayRows.value.length === 0)

const pendingProductsCount = computed(() => {
  const { pendingCreateIds, pendingUpdateIds } = pendingSyncMap.value
  return pendingCreateIds.size + pendingUpdateIds.size
})

async function refreshPendingSyncState() {
  pendingSyncMap.value = await getPendingProductSyncMap()
}

function formatStockQty(row) {
  const n = Number(row._stockQty ?? 0)
  const loc = numberLocale()
  const unit = unitOptions.value.find((u) => u.value === row.unit)?.label || row.unit || ''
  return `${n.toLocaleString(loc, { maximumFractionDigits: 3 })} ${unit}`.trim()
}


/** Yangi mahsulot: nom bo‘yicha bazadagi o‘xshashlar (masalan «cola»). */
const nameSuggestions = computed(() => {
  if (editingId.value) return []
  const q = form.name.trim().toLowerCase()
  if (q.length < 2) return []
  const list = rows.value.filter((r) => (r.name || '').toLowerCase().includes(q))
  list.sort((a, b) =>
    (a.name || '').localeCompare(b.name || '', collatorLocaleForUi(locale.value)),
  )
  return list.slice(0, 30)
})

/** Yangi mahsulot: to‘liq nom dublikati (registr farqi yo‘q). */
const nameDuplicateNew = computed(() => {
  if (editingId.value) return false
  const n = form.name.trim().toLowerCase()
  if (!n) return false
  return rows.value.some((r) => (r.name || '').trim().toLowerCase() === n)
})

function pickExistingProduct(row) {
  openEdit(row)
}

function applyStockMapFromQuantities(productRows, quantityByProductId = {}) {
  const map = {}
  for (const row of productRows) {
    const qty = Number(quantityByProductId[row.id] ?? 0)
    const min = Number(row.min_stock ?? 0)
    map[row.id] = {
      quantity: qty,
      is_low: qty <= min,
      min_stock: min,
    }
  }
  stockMap.value = map
}

async function loadFromIndexedDBCache({ skipPrune = false } = {}) {
  await hydrateOrganizationStore(org)
  const { orgId, branchId } = await resolvePosIds(org)
  if (!orgId) return { hadCache: false, syncedAt: null }

  const cached = await loadCatalogFromIndexedDB(orgId, branchId, {
    refreshFromApi: false,
    skipPrune,
  })
  if (!cached.hasCache && !cached.products?.length) {
    return { hadCache: false, syncedAt: cached.syncedAt ?? null }
  }

  const nextProducts = sortProductsForDisplay(cached.products)
  await applyProductsListIfChanged(nextProducts)
  if (cached.categories?.length || !categoryList.value.length) {
    categoryList.value = cached.categories
  }
  applyStockMapFromQuantities(rows.value, cached.stockMap)
  return { hadCache: true, syncedAt: cached.syncedAt ?? null }
}

function applyStockFromApiResponse(stockData) {
  const map = {}
  for (const row of stockData?.results || []) {
    map[row.product] = {
      quantity: Number(row.quantity ?? 0),
      is_low: Boolean(row.is_low),
      min_stock: Number(row.min_stock ?? 0),
    }
  }
  stockMap.value = map
}

function mergeCreatedProductRow(created) {
  if (!created?.id) return
  const id = Number(created.id)
  const list = rows.value.filter((r) => Number(r.id) !== id)
  rows.value = sortProductsForDisplay([created, ...list])
  const qty = Number(created._initialStock ?? 0)
  const min = Number(created.min_stock ?? 0)
  if (org.currentBranchId) {
    stockMap.value = {
      ...stockMap.value,
      [id]: { quantity: qty, is_low: qty <= min, min_stock: min },
    }
  }
}

/** Ro‘yxat o‘zgarmagan bo‘lsa qayta chizmaydi (kesh → API ikki marta emas). */
async function applyProductsListIfChanged(pList) {
  if (!Array.isArray(pList)) {
    throw new Error('Mahsulotlar ro‘yxati noto‘g‘ri javob qaytardi')
  }
  const guard = await getPendingCatalogGuardIds()
  const idMap = await getProductIdMap()
  const next = dedupeCatalogProductRows(pList, guard, idMap)
  const nextSig = productIdsSignature(next)
  const curSig = productIdsSignature(rows.value)
  if (curSig && nextSig && curSig === nextSig) {
    return false
  }
  rows.value = sortProductsForDisplay(next)
  return true
}

let attachImagesPromise = null

function attachProductImagesOnce() {
  if (!rows.value.length) return Promise.resolve()
  if (attachImagesPromise) return attachImagesPromise
  attachImagesPromise = attachCachedImagesToProducts(rows.value)
    .then((next) => {
      const curSig = productIdsSignature(rows.value)
      const nextSig = productIdsSignature(next)
      if (curSig === nextSig) {
        const hasNewUrls = next.some(
          (p, i) => p._cachedImageUrl && p._cachedImageUrl !== rows.value[i]?._cachedImageUrl,
        )
        if (hasNewUrls) {
          rows.value = sortProductsForDisplay(next)
        }
      } else {
        rows.value = sortProductsForDisplay(next)
      }
    })
    .finally(() => {
      attachImagesPromise = null
    })
  return attachImagesPromise
}

let fetchInFlight = null
let lastSyncRefreshAt = 0

function setTableLoading(active) {
  if (active && hasDisplayedProducts.value) return
  loading.value = active
}

function markProductsDisplayed() {
  loading.value = false
  if (rows.value.length > 0) {
    hasDisplayedProducts.value = true
  }
}

function productIdsSignature(list) {
  if (!list?.length) return ''
  return list.map((p) => p.id).join(',')
}

async function refreshCatalogFromApi() {
  const { orgId, branchId } = await resolvePosIds(org)
  if (orgId) {
    pruneStaleOfflineCatalog(orgId).catch(() => {})
  }

  const branchIdForStock = org.currentBranchId

  try {
    await syncOfflineMutations().catch((err) => {
      console.warn('[offline] kutilayotgan mahsulotlar sinxroni:', err)
    })

    const [pList, cList, stockData] = await Promise.all([
      products.list(),
      categories.list(),
      branchIdForStock
        ? stockLevels.list({ branch: branchIdForStock })
        : Promise.resolve({ results: [] }),
    ])

    markApiReachable()
    isOnline.value = true
    catalogOffline.value = false

    await applyProductsListIfChanged(pList)
    if (cList?.length || !categoryList.value.length) {
      categoryList.value = cList || []
    }
    applyStockFromApiResponse(stockData)
    markProductsDisplayed()

    attachProductImagesOnce()

    if (orgId && branchId) {
      persistCatalogToIndexedDB(orgId, branchId, pList, cList, stockData).catch((err) => {
        console.warn('[catalog] kesh yangilash:', err)
      })
    }

    cacheProductImages(rows.value, { concurrency: 3 })
      .then((r) => {
        if (r.cached) attachProductImagesOnce()
      })
      .catch(() => {})
  } catch (err) {
    console.warn('[products] yuklash:', err)
    const ok = await checkApiReachable()
    isOnline.value = ok
    if (!rows.value.length) {
      const { hadCache: restored } = await loadFromIndexedDBCache()
      catalogOffline.value = restored || rows.value.length > 0
      if (!rows.value.length) {
        apiError.value = ok
          ? 'Mahsulotlar yuklanmadi. Qayta urinib ko‘ring.'
          : 'Server bilan bog‘lanib bo‘lmadi va lokal kesh bo‘sh.'
      }
    } else {
      catalogOffline.value = !ok
    }
    markProductsDisplayed()
  }
}

async function fetchData() {
  if (fetchInFlight) return fetchInFlight

  fetchInFlight = (async () => {
    apiError.value = ''

    if (auth.organizationId) {
      localStorage.setItem('organization_id', String(auth.organizationId))
    }

    await Promise.all([
      refreshPendingSyncState(),
      hydrateOrganizationStore(org),
    ])

    const cacheLoad = await loadFromIndexedDBCache({ skipPrune: true })
    if (cacheLoad.hadCache) {
      markProductsDisplayed()
      attachProductImagesOnce()
      if (typeof navigator !== 'undefined' && navigator.onLine) {
        refreshCatalogFromApi().catch((err) => {
          console.warn('[products] fon yangilash:', err)
        })
      }
      return
    }

    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      isOnline.value = false
      catalogOffline.value = false
      apiError.value =
        'Offline rejim — mahsulotlar keshda yo‘q. Avval backend yoqilgan holda Kassa yoki shu sahifani oching.'
      markProductsDisplayed()
      return
    }

    if (!hasDisplayedProducts.value && !rows.value.length) {
      setTableLoading(true)
    }

    await refreshCatalogFromApi()
  })().finally(() => {
    fetchInFlight = null
  })

  return fetchInFlight
}

/** `savdopro:sync-complete` — faqat sinxron belgisi; jadvalni qayta yuklamaydi. */
async function refreshFromSyncEvent() {
  if (fetchInFlight) return
  const now = Date.now()
  if (now - lastSyncRefreshAt < 4000) return
  lastSyncRefreshAt = now
  await refreshPendingSyncState()
  if (hasDisplayedProducts.value || rows.value.length) {
    await loadFromIndexedDBCache({ skipPrune: true })
    markProductsDisplayed()
    refreshCatalogFromApi().catch(() => {})
  }
}

async function refreshStockForBranch() {
  const branchId = org.currentBranchId
  if (!branchId) {
    stockMap.value = {}
    return
  }
  if (isOfflineMode()) {
    const cachedQty = await loadStockMapFromIndexedDB(branchId)
    if (Object.keys(cachedQty).length) {
      applyStockMapFromQuantities(rows.value, cachedQty)
    }
    return
  }
  try {
    const stockData = await stockLevels.list({ branch: branchId })
    applyStockFromApiResponse(stockData)
  } catch {
    const cachedQty = await loadStockMapFromIndexedDB(branchId)
    if (Object.keys(cachedQty).length) {
      applyStockMapFromQuantities(rows.value, cachedQty)
    }
  }
}

async function refreshCategories() {
  if (isOfflineMode()) {
    await loadFromIndexedDBCache()
    return
  }
  categoryList.value = await categories.list()
}

async function quickCreateCategory() {
  categoryQuickError.value = ''
  const name = newCategoryName.value.trim()
  if (!name) return
  categorySaving.value = true
  try {
    const { orgId } = await resolvePosIds(org)
    const created = isOfflineMode()
      ? await offlineCreateCategory(orgId, { name })
      : await categories.create({ name })
    await refreshCategories()
    form.category = String(created.id)
    newCategoryName.value = ''
    showQuickCategory.value = false
  } catch (error) {
    const data = error?.response?.data
    categoryQuickError.value = error?._notifyHandled
      ? ''
      : resolveApiError(error, tr, tr('page.products.categoryCreateFail'))
  } finally {
    categorySaving.value = false
  }
}

function toggleQuickCategory() {
  showQuickCategory.value = !showQuickCategory.value
  categoryQuickError.value = ''
}

function resetForm() {
  form.name = ''
  form.category = ''
  form.sku = ''
  form.barcode = ''
  form.unit = 'piece'
  form.sell_price = '0'
  form.cost_price = '0'
  form.min_stock = '0'
  form.quantity = '0'
  form.branch = org.currentBranchId || ''
  imageFile.value = null
  clearProductImage.value = false
  revokeImageBlobPreview()
  imagePreviewUrl.value = ''
  editingHadImage.value = false
  if (productImageInput.value) productImageInput.value.value = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  apiError.value = ''
  categoryQuickError.value = ''
  newCategoryName.value = ''
  showQuickCategory.value = categoryList.value.length === 0
  modalOpen.value = true
}

function openEdit(row) {
  editingId.value = row.id
  editingHadImage.value = Boolean(row.image_url)
  imageFile.value = null
  clearProductImage.value = false
  revokeImageBlobPreview()
  imagePreviewUrl.value = productRowImageSrc(row) || ''
  if (productImageInput.value) productImageInput.value.value = ''
  form.name = row.name || ''
  form.category = row.category != null && row.category !== '' ? String(row.category) : ''
  form.sku = row.sku || ''
  form.barcode = row.barcode || ''
  form.unit = row.unit || 'piece'
  form.sell_price = String(row.sell_price ?? '0')
  form.cost_price = String(row.cost_price ?? '0')
  form.min_stock = String(row.min_stock ?? '0')
  form.quantity = '0'
  form.branch = row.branch || org.currentBranchId || ''
  apiError.value = ''
  categoryQuickError.value = ''
  newCategoryName.value = ''
  showQuickCategory.value = false
  modalOpen.value = true
}

function buildPayload() {
  const payload = {
    name: form.name,
    category: form.category || null,
    sku: form.sku || '',
    barcode: form.barcode || '',
    unit: form.unit,
    sell_price: form.sell_price || 0,
    cost_price: form.cost_price || 0,
    min_stock: form.min_stock || 0,
    branch: form.branch || null,
  }
  if (!editingId.value) {
    payload.initial_quantity = form.quantity || 0
  }
  return payload
}

async function submit() {
  apiError.value = ''
  if (!editingId.value && nameDuplicateNew.value) {
    apiError.value = 'Bu nomdagi mahsulot allaqachon mavjud.'
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    const { orgId, branchId } = await resolvePosIds(org)
    if (!payload.branch && branchId) payload.branch = branchId

    if (isOfflineMode()) {
      if (imageFile.value || clearProductImage.value) {
        apiError.value = 'Offline: rasm server yoqilganda sinxronlanadi. Boshqa maydonlar saqlanadi.'
      }
      if (editingId.value) {
        await offlineUpdateProduct(editingId.value, payload, {
          imageFile: imageFile.value,
          clearImage: clearProductImage.value,
        })
      } else {
        const created = await offlineCreateProduct(orgId, payload, { imageFile: imageFile.value })
        const qty = Number(payload.initial_quantity ?? 0)
        const min = Number(payload.min_stock ?? 0)
        if (branchId && created?.id != null) {
          stockMap.value = {
            ...stockMap.value,
            [created.id]: { quantity: qty, is_low: qty <= min, min_stock: min },
          }
        }
      }
      modalOpen.value = false
      await refreshPendingSyncState()
      await fetchData()
      return
    }

    const multipart =
      Boolean(imageFile.value) || Boolean(editingId.value && clearProductImage.value)
    if (editingId.value) {
      if (multipart) {
        await products.update(editingId.value, payload, {
          image: imageFile.value,
          clearImage: clearProductImage.value,
        })
      } else {
        await products.update(editingId.value, payload)
      }
    } else if (imageFile.value) {
      const created = await products.create(payload, { image: imageFile.value })
      mergeCreatedProductRow({
        ...created,
        _initialStock: Number(payload.initial_quantity ?? 0),
      })
    } else {
      const created = await products.create(payload)
      mergeCreatedProductRow({
        ...created,
        _initialStock: Number(payload.initial_quantity ?? 0),
      })
    }
    modalOpen.value = false
    filters.syncStatus = ''
    search.value = ''
    await fetchData()
  } catch (error) {
    apiError.value = error?._notifyHandled
      ? ''
      : resolveApiError(error, tr, tr('page.products.saveError'))
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (isOfflineMode()) {
    showMessage(tr('page.products.deleteOfflineOnly'))
    return
  }
  if (!confirm(`"${row.name}" mahsuloti o‘chirilsinmi?`)) return
  try {
    const { orgId } = await resolvePosIds(org)
    const id = Number(row.id)
    if (Number.isFinite(id) && id > 0) {
      await products.remove(id)
    }
    if (orgId) {
      await purgeProductFromLocalCache(orgId, id)
    }
    await fetchData()
  } catch (error) {
    showApiError(error, 'page.products.deleteFail')
  }
}

function openScanner(target) {
  scanTarget.value = target
  scannerOpen.value = true
}

function onScanned(value) {
  if (scanTarget.value === 'barcode') {
    form.barcode = value
  } else if (scanTarget.value === 'search') {
    search.value = value
  }
  scannerOpen.value = false
}

function onImageFileChange(event) {
  const file = event.target.files?.[0]
  if (!file) return
  if (file.size > 3 * 1024 * 1024) {
    apiError.value = 'Rasm 3 MB dan katta.'
    event.target.value = ''
    return
  }
  clearProductImage.value = false
  imageFile.value = file
  setImagePreviewFromFile(file)
}

function resetPickedImageFile() {
  imageFile.value = null
  if (productImageInput.value) productImageInput.value.value = ''
  if (editingId.value && editingHadImage.value && !clearProductImage.value) {
    const row = rows.value.find((r) => r.id === editingId.value)
    revokeImageBlobPreview()
    imagePreviewUrl.value = row ? productRowImageSrc(row) : ''
  } else {
    revokeImageBlobPreview()
    imagePreviewUrl.value = ''
  }
}

watch(modalOpen, (open) => {
  if (!open) {
    imageFile.value = null
    clearProductImage.value = false
    revokeImageBlobPreview()
    imagePreviewUrl.value = ''
    if (productImageInput.value) productImageInput.value.value = ''
  }
})

watch(clearProductImage, (cleared) => {
  if (cleared) {
    imageFile.value = null
    if (productImageInput.value) productImageInput.value.value = ''
    revokeImageBlobPreview()
    imagePreviewUrl.value = ''
  } else if (editingId.value) {
    const row = rows.value.find((r) => r.id === editingId.value)
    revokeImageBlobPreview()
    imagePreviewUrl.value = row ? productRowImageSrc(row) : ''
  }
})

watch(() => org.currentBranchId, () => {
  refreshStockForBranch()
})

let unsubscribeConnectivity = null

async function onConnectivityChanged(offline, { skipFetch = false } = {}) {
  isOnline.value = !offline
  if (offline) {
    const { hadCache } = await loadFromIndexedDBCache()
    catalogOffline.value = hadCache || rows.value.length > 0
    return
  }
  if (skipFetch) return
  if (hasDisplayedProducts.value || rows.value.length) {
    refreshCatalogFromApi().catch(() => {})
    return
  }
  await fetchData()
}

function onSyncComplete() {
  refreshFromSyncEvent().catch(() => {})
}

function loadProductsPage() {
  if (rows.value.length || hasDisplayedProducts.value) {
    markProductsDisplayed()
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      return Promise.resolve()
    }
    return refreshCatalogFromApi()
  }
  return fetchData()
}

onMounted(() => {
  loadProductsPage().catch(() => {})

  let skipInitialConnectivityFetch = true
  unsubscribeConnectivity = onConnectivityChange((offline) => {
    const skipFetch = skipInitialConnectivityFetch
    skipInitialConnectivityFetch = false
    onConnectivityChanged(offline, { skipFetch })
  })
  window.addEventListener('savdopro:sync-complete', onSyncComplete)
})

onUnmounted(() => {
  unsubscribeConnectivity?.()
  window.removeEventListener('savdopro:sync-complete', onSyncComplete)
  revokeImageBlobPreview()
})
</script>

<template>
  <div class="products-view">
    <PageHeader
      :title="tr('page.products.title')"
      :subtitle="tr('page.products.subtitle')"
    >
      <template #actions>
        <button
          type="button"
          class="btn btn--primary products-view__add"
          :title="!isOnline ? tr('page.products.offlineHint') : ''"
          @click="openCreate"
        >
          <span class="products-view__add-icon" aria-hidden="true">+</span>
          {{ tr('page.products.addNew') }}
        </button>
      </template>
    </PageHeader>

    <p v-if="apiError && !tableLoading" class="form-message form-message--error products-view__fetch-error">
      {{ apiError }}
    </p>

    <p
      v-if="pendingProductsCount > 0"
      class="products-view__sync-banner"
      role="status"
    >
      {{ tr('page.products.syncBanner', { n: pendingProductsCount }) }}
    </p>

    <div class="products-view__toolbar card">
      <select v-model="filters.syncStatus" class="products-view__filter-select">
        <option value="">{{ tr('page.products.filterAllStatuses') }}</option>
        <option v-for="opt in syncStatusFilterOptions" :key="opt.code" :value="opt.code">
          {{ opt.label }}
        </option>
      </select>
      <div class="products-view__search-wrap">
        <span class="products-view__search-icon" aria-hidden="true">⌕</span>
        <input
          v-model="search"
          class="products-view__search"
          type="search"
          :placeholder="tr('page.products.searchPlaceholder')"
        />
      </div>
      <button class="btn btn--ghost products-view__scan" type="button" @click="openScanner('search')">
        <span aria-hidden="true">▣</span>
        {{ tr('page.products.btnScanner') }}
      </button>
    </div>

    <div class="products-view__table card">
      <DataTable
        :columns="columns"
        :rows="displayRows"
        :loading="tableLoading"
        clickable
        actions-label=""
        :empty-text="tr('page.products.emptyTable')"
        @row-click="openEdit"
      >
        <template #cell:image_url="{ row }">
          <div class="products-view__thumb-wrap">
            <img
              v-if="productRowHasImage(row)"
              class="products-view__thumb"
              :src="productRowImageSrc(row)"
              :alt="row.name || ''"
              loading="lazy"
            />
            <span
              v-else
              class="products-view__thumb--empty"
              :title="row.name || ''"
              aria-hidden="true"
            >{{ productRowInitials(row) }}</span>
          </div>
        </template>
        <template #cell:name="{ row }">
          <div class="products-view__name-cell">
            <span class="products-view__name-primary">{{ row.name || '—' }}</span>
          </div>
        </template>
        <template #cell:_stockQty="{ row }">
          <span
            class="products-view__stock"
            :class="{ 'products-view__stock--low': row._stockLow }"
          >
            {{ org.currentBranchId ? formatStockQty(row) : '—' }}
          </span>
        </template>
        <template #cell:_syncStatus="{ row }">
          <SyncStatusIcon
            :kind="productSyncIconKind(row._syncStatus)"
            :label="syncStatusLabelMap[row._syncStatus] || row._syncStatus"
          />
        </template>
        <template #actions="{ row }">
          <button
            type="button"
            class="products-view__del"
            :title="tr('page.products.deleteAria')"
            :aria-label="tr('page.products.deleteAria')"
            @click.stop="remove(row)"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
              <path
                d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
              <path d="M10 11v6M14 11v6" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </button>
        </template>
      </DataTable>
    </div>

    <AppModal
      :open="modalOpen"
      :title="editingId ? tr('page.products.modalEditTitle') : tr('page.products.modalNewTitle')"
      width="min(92vw, 720px)"
      @close="modalOpen = false"
    >
      <form class="products-form" @submit.prevent="submit">
        <section class="products-form__section">
          <h4 class="products-form__heading">Asosiy</h4>
          <label class="field">
            <span>Mahsulot nomi <i class="required">*</i></span>
            <input v-model.trim="form.name" type="text" required maxlength="255" />
            <p v-if="!editingId && nameDuplicateNew" class="form-message form-message--error name-duplicate-msg">
              Bu nom allaqachon mavjud — saqlab bo‘lmaydi. Pastdagi ro‘yxatdan tanlang yoki nomni o‘zgartiring.
            </p>
            <div
              v-if="!editingId && form.name.trim().length >= 2 && nameSuggestions.length"
              class="name-suggest"
            >
              <span class="name-suggest__title">Bazada o‘xshash mahsulotlar</span>
              <ul class="name-suggest__list">
                <li v-for="r in nameSuggestions" :key="r.id">
                  <button type="button" class="name-suggest__btn" @click="pickExistingProduct(r)">
                    <span class="name-suggest__name">{{ r.name }}</span>
                    <span v-if="r.sku" class="name-suggest__meta">{{ r.sku }}</span>
                  </button>
                </li>
              </ul>
            </div>
          </label>
        </section>

        <section class="products-form__section">
          <h4 class="products-form__heading">Rasm</h4>
          <div class="product-image-field">
            <div
              v-if="imagePreviewUrl && !clearProductImage"
              class="product-image-field__preview"
            >
              <img :src="imagePreviewUrl" alt="" />
            </div>
            <div v-else class="product-image-field__preview product-image-field__preview--empty">
              Rasm yo‘q
            </div>
            <div class="product-image-field__row">
              <label class="btn btn--ghost btn--sm product-image-field__pick">
                <input
                  ref="productImageInput"
                  type="file"
                  class="product-image-field__input"
                  accept="image/jpeg,image/png,image/webp,image/gif"
                  @change="onImageFileChange"
                />
                Rasm tanlash
              </label>
              <button
                v-if="imageFile"
                type="button"
                class="btn btn--ghost btn--sm"
                @click="resetPickedImageFile"
              >
                Tanlovni bekor
              </button>
            </div>
            <label v-if="editingId && editingHadImage" class="product-image-field__clear">
              <input v-model="clearProductImage" type="checkbox" />
              <span>Rasmni olib tashlash</span>
            </label>
            <p class="product-image-field__hint">JPEG, PNG, WebP yoki GIF, 3 MB gacha.</p>
          </div>
        </section>

        <section class="products-form__section">
          <div class="products-form__row">
            <label class="field">
              <span>Filial</span>
              <select v-model="form.branch">
                <option value="">— Hammasi —</option>
                <option v-for="b in org.branches" :key="b.id" :value="String(b.id)">{{ branchLabel(b) }}</option>
              </select>
            </label>
            <label class="field">
              <span>Minimal qoldiq</span>
              <input v-model="form.min_stock" type="number" min="0" step="0.001" />
            </label>
          </div>

          <label v-if="!editingId" class="field products-form__field-spaced">
            <span>Boshlang‘ich miqdor</span>
            <input v-model="form.quantity" type="number" min="0" step="0.001" />
          </label>

          <label class="field products-form__field-spaced">
            <div class="category-row">
              <select
                v-model="form.category"
                class="category-row__select"
                aria-label="Kategoriya"
              >
                <option value="">— Tanlanmagan —</option>
                <option v-for="c in categoryList" :key="c.id" :value="String(c.id)">{{ c.name }}</option>
              </select>
              <button
                type="button"
                class="btn btn--ghost btn--sm category-row__btn"
                @click="toggleQuickCategory"
              >
                {{ showQuickCategory ? '▼' : '+' }} Yangi kategoriya
              </button>
            </div>
            <div v-if="showQuickCategory" class="quick-category">
              <p v-if="!categoryList.length" class="quick-category__hint">
                Hozircha kategoriya yo‘q. Nom yozib «Kategoriya qo‘shish» — keyin mahsulotni davom ettirasiz.
              </p>
              <div class="quick-category__row">
                <input
                  v-model.trim="newCategoryName"
                  type="text"
                  maxlength="120"
                  class="quick-category__input"
                  placeholder="Masalan, Ichimliklar, Non mahsulotlari…"
                  @keydown.enter.prevent="quickCreateCategory"
                />
                <button
                  type="button"
                  class="btn btn--primary btn--sm"
                  :disabled="categorySaving || !newCategoryName.trim()"
                  @click="quickCreateCategory"
                >
                  {{ categorySaving ? '…' : 'Kategoriya qo‘shish' }}
                </button>
              </div>
              <p v-if="categoryQuickError" class="form-message form-message--error quick-category__err">
                {{ categoryQuickError }}
              </p>
            </div>
          </label>
        </section>

        <section class="products-form__section">
          <div class="products-form__row">
            <label class="field">
              <span>Birlik</span>
              <select v-model="form.unit">
                <option v-for="u in unitOptions" :key="u.value" :value="u.value">{{ u.label }}</option>
              </select>
            </label>
            <label class="field">
              <span>SKU</span>
              <input v-model.trim="form.sku" type="text" maxlength="64" />
            </label>
          </div>
          <label class="field products-form__field-spaced">
            <span>Shtrix-kod</span>
            <div class="input-with-action">
              <input v-model.trim="form.barcode" type="text" maxlength="64" />
              <button
                class="btn btn--ghost btn--sm"
                type="button"
                :title="tr('page.products.scanCameraTitle')"
                @click="openScanner('barcode')"
              >
                ▣
              </button>
            </div>
          </label>
        </section>

        <section class="products-form__section products-form__section--prices">
          <h4 class="products-form__heading">Narxlar</h4>
          <div class="products-form__row">
            <label class="field">
              <span>Sotuv narxi (so‘m) <i class="required">*</i></span>
              <input v-model="form.sell_price" type="number" min="0" step="0.01" required />
            </label>
            <label class="field">
              <span>Tan narxi (so‘m)</span>
              <input v-model="form.cost_price" type="number" min="0" step="0.01" placeholder="0" />
            </label>
          </div>
        </section>

        <p v-if="apiError" class="form-message form-message--error products-form__error">{{ apiError }}</p>
      </form>

      <template #footer>
        <div class="products-form__footer">
          <button class="btn btn--ghost" type="button" @click="modalOpen = false">Bekor qilish</button>
          <button
            class="btn btn--primary"
            :disabled="saving || (!editingId && nameDuplicateNew)"
            @click="submit"
          >
            {{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
          </button>
        </div>
      </template>
    </AppModal>

    <BarcodeScanner
      :open="scannerOpen"
      :title="scanTarget === 'search' ? tr('page.products.scanTitleSearch') : tr('page.products.scanTitleBarcode')"
      @close="scannerOpen = false"
      @scanned="onScanned"
    />
  </div>
</template>

<style scoped>
.products-view__fetch-error {
  margin: 0 0 12px;
}

.products-view__thumb-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
}

.products-view__thumb {
  width: 56px;
  height: 56px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid var(--line, #e2e8f0);
  background: #f1f5f9;
  vertical-align: middle;
}

.products-view__thumb--empty {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 10px;
  background: linear-gradient(145deg, #e2e8f0 0%, #cbd5e1 100%);
  color: #475569;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  border: 1px solid var(--line, #e2e8f0);
}

.products-view__name-cell {
  min-width: 0;
}

.products-view__name-primary {
  display: block;
  font-weight: 600;
  font-size: 0.95rem;
  line-height: 1.35;
  color: var(--text, #0f172a);
  word-break: break-word;
}

.products-view__stock {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text, #0f172a);
  white-space: nowrap;
}

.products-view__stock--low {
  color: #b91c1c;
}

.products-view__sync-banner {
  margin: 0 0 12px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  background: #fff4d6;
  color: #8a6708;
  font-size: 0.9rem;
  font-weight: 500;
}

.products-view__toolbar .products-view__filter-select {
  min-width: 180px;
}

.product-image-field {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.product-image-field__preview {
  width: 100%;
  max-width: 220px;
  aspect-ratio: 1;
  border-radius: 12px;
  border: 1px solid var(--line, #e2e8f0);
  overflow: hidden;
  background: var(--surface-soft, #f8fafc);
  display: grid;
  place-items: center;
}

.product-image-field__preview img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.product-image-field__preview--empty {
  color: var(--text-muted, #64748b);
  font-size: 0.9rem;
}

.product-image-field__row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.product-image-field__pick {
  cursor: pointer;
  position: relative;
}

.product-image-field__input {
  position: absolute;
  inset: 0;
  opacity: 0;
  width: 100%;
  height: 100%;
  cursor: pointer;
}

.product-image-field__clear {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
  cursor: pointer;
  user-select: none;
}

.product-image-field__hint {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted, #64748b);
}

/* Mahsulot modali — bo‘limlar, 2 ustunli qatorlar */
.products-form {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.products-form__section {
  margin: 0;
  padding: 0;
  border: 0;
}

.products-form__heading {
  margin: 0 0 10px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.products-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  align-items: start;
}

.products-form__field-spaced {
  margin-top: 4px;
  display: grid;
  gap: 6px;
}

.products-form__section--prices {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: linear-gradient(165deg, #f8fafc 0%, #fff 55%);
}

.products-form__section--prices .products-form__heading {
  margin-bottom: 12px;
}

.products-form__error {
  margin: 0;
}

.products-form__footer {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
  width: 100%;
}

@media (max-width: 560px) {
  .products-form__row {
    grid-template-columns: 1fr;
  }
}

.products-view__add {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  box-shadow: 0 2px 10px rgba(31, 79, 163, 0.22);
}

.products-view__add-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.2);
  font-weight: 700;
  font-size: 1.1rem;
  line-height: 1;
}

.products-view__scan {
  flex-shrink: 0;
}

.products-view__del {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  margin: 0 auto;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition:
    color 0.16s ease,
    background 0.16s ease,
    border-color 0.16s ease,
    transform 0.14s ease;
}

.products-view__del:hover {
  color: var(--danger);
  background: rgba(187, 45, 59, 0.08);
  border-color: rgba(187, 45, 59, 0.2);
  transform: scale(1.06);
}

.products-view__del:active {
  transform: scale(0.96);
}

.name-duplicate-msg {
  margin-top: 8px;
}

.name-suggest {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--surface-soft);
  border: 1px solid var(--line);
  max-height: 220px;
  overflow-y: auto;
}

.name-suggest__title {
  display: block;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.name-suggest__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name-suggest__btn {
  width: 100%;
  text-align: left;
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 10px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  background: #fff;
  cursor: pointer;
  font: inherit;
  color: var(--text);
}

.name-suggest__btn:hover {
  border-color: #7ea4e6;
  background: #f8fafd;
}

.name-suggest__name {
  font-weight: 500;
}

.name-suggest__meta {
  font-size: 0.82rem;
  color: var(--text-muted);
}

.field-hint {
  display: block;
  margin-top: 6px;
  font-size: 0.82rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.input-with-action {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.input-with-action input {
  flex: 1;
  min-width: 0;
}

.input-with-action .btn {
  flex-shrink: 0;
  align-self: stretch;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 44px;
  padding-left: 10px;
  padding-right: 10px;
}

.category-row {
  display: flex;
  gap: 8px;
  align-items: stretch;
}

.category-row__select {
  flex: 1;
  min-width: 0;
}

.category-row__btn {
  flex-shrink: 0;
  white-space: nowrap;
}

.quick-category {
  margin-top: 10px;
  padding: 12px;
  border-radius: var(--radius-sm);
  background: var(--surface-soft);
  border: 1px dashed var(--line);
}

.quick-category__hint {
  margin: 0 0 10px;
  font-size: 0.86rem;
  color: var(--text-muted);
  line-height: 1.45;
}

.quick-category__row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.quick-category__input {
  flex: 1;
  min-width: 160px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: 0.92rem;
  outline: none;
}

.quick-category__input:focus {
  border-color: #7ea4e6;
  background: #fff;
}

.quick-category__err {
  margin: 8px 0 0;
}

@media (max-width: 540px) {
  .products-view__scan span {
    display: none;
  }
}
</style>

<style>
[data-theme='dark'] .products-view {
  --text: #f1f5f9;
  --text-muted: #94a3b8;
  --line: #334155;
  --surface: #1e293b;
  --surface-soft: #0f172a;
  color: var(--text);
}
</style>
