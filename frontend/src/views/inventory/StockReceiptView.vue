<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import AppModal from '../../components/AppModal.vue'
import BarcodeScanner from '../../components/BarcodeScanner.vue'
import MobileCameraScanFab from '../../components/MobileCameraScanFab.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import SyncStatusIcon from '../../components/SyncStatusIcon.vue'
import { useHardwareBarcodeScanner } from '../../composables/useHardwareBarcodeScanner'
import { findProductByScanCode, normalizeScanCode } from '../../lib/barcodeScan'
import { sortProductsForDisplay } from '../../lib/productSort'
import {
  loadCatalogFromIndexedDB,
  persistCatalogToIndexedDB,
} from '../../offline/catalogSync'
import {
  checkApiReachable,
  isOfflineMode,
  isNetworkError,
  markApiReachable,
  onConnectivityChange,
} from '../../offline/connectivity'
import { hydrateOrganizationStore, resolvePosIds } from '../../offline/posContext'
import {
  attachCachedImagesToProducts,
  cacheProductImages,
  resolveProductImageSrc,
} from '../../offline/imageCache'
import {
  countPendingStockReceipts,
  getPendingStockReceiptMap,
  saveOfflineStockReceipt,
} from '../../offline/offlineStockReceipts'
import { useI18n } from '../../i18n'
import { categories, products as productsApi } from '../../services/catalog.service'
import { stockLevels, stockMovements } from '../../services/inventory.service'
import { routeWithPosShell } from '../../posShellQuery'
import { useAuthStore } from '../../stores/auth'
import { useOrganizationStore } from '../../stores/organization'

const router = useRouter()
const auth = useAuthStore()
const org = useOrganizationStore()
const { tr, locale, branchLabel } = useI18n()

const rows = ref([])
const pendingReceiptCount = ref(0)
const loading = ref(false)
const hasDisplayedProducts = ref(false)
let fetchInFlight = null
let lastSyncRefreshAt = 0
let branchFilterReady = false
let unsubscribeConnectivity = null
const search = ref('')
const branchFilter = ref('')
const modalOpen = ref(false)
const scannerOpen = ref(false)
const selectedProduct = ref(null)
const qtyInputRef = ref(null)
const hardwareScanRef = ref(null)
const hardwareScanValue = ref('')
const saving = ref(false)
const apiError = ref('')
const successMsg = ref('')

const receiptForm = reactive({
  branch: '',
  quantity: '1',
  unit_cost: '0',
  note: '',
})

const unitOptions = computed(() => [
  { value: 'piece', label: tr('page.products.unit.piece') },
  { value: 'kg', label: tr('page.products.unit.kg') },
  { value: 'liter', label: tr('page.products.unit.liter') },
  { value: 'pack', label: tr('page.products.unit.pack') },
])

const syncStatusLabelMap = computed(() => ({
  pending: tr('page.receipt.sync.pending'),
  synced: tr('page.receipt.sync.synced'),
}))

function receiptSyncIconKind(status) {
  return status === 'pending' ? 'pending' : 'synced'
}

function numberLocale() {
  return locale.value === 'ru' ? 'ru-RU' : 'uz-UZ'
}

function productRowImageSrc(row) {
  if (!row) return ''
  if (row._cachedImageUrl) return row._cachedImageUrl
  if (isOfflineMode()) return ''
  return resolveProductImageSrc(row)
}

function productRowHasImage(row) {
  if (!row || row._imageLoadError) return false
  return Boolean(productRowImageSrc(row))
}

function onProductImageError(row) {
  if (!row) return
  row._imageLoadError = true
}

function onProductImageLoad(row) {
  if (!row) return
  row._imageLoadError = false
}

function formatStockQty(row) {
  const n = Number(row._stockQty ?? 0)
  const unit = unitOptions.value.find((u) => u.value === row.unit)?.label || row.unit || ''
  return `${n.toLocaleString(numberLocale(), { maximumFractionDigits: 3 })} ${unit}`.trim()
}

const columns = computed(() => {
  const loc = numberLocale()
  return [
    {
      key: '_syncStatus',
      label: tr('page.receipt.colSync'),
      width: '52px',
    },
    {
      key: 'image_url',
      label: tr('page.products.colImage'),
      width: '84px',
    },
    { key: 'name', label: tr('page.products.colName') },
    {
      key: '_categoryName',
      label: tr('page.products.colCategory'),
      width: '160px',
    },
    { key: 'sku', label: 'SKU', width: '120px' },
    {
      key: '_stockQty',
      label: tr('page.products.colStock'),
      width: '120px',
    },
    {
      key: 'cost_price',
      label: tr('page.products.colCost'),
      formatter: (v) => Number(v ?? 0).toLocaleString(loc),
      width: '100px',
    },
  ]
})

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter(
    (r) =>
      r.name?.toLowerCase().includes(q) ||
      r.sku?.toLowerCase().includes(q) ||
      r.barcode?.toLowerCase().includes(q),
  )
})

const tableLoading = computed(() => loading.value && filteredRows.value.length === 0)

const lineTotal = computed(() => {
  const q = Number(receiptForm.quantity || 0)
  const c = Number(receiptForm.unit_cost || 0)
  return q * c
})

function focusHardwareScan() {
  if (modalOpen.value || scannerOpen.value) return
  nextTick(() => hardwareScanRef.value?.focus())
}

function processScanCode(raw) {
  hardwareScanValue.value = ''
  const product = findProductByScanCode(rows.value, raw)
  if (product) {
    openReceiptModal(product)
    return true
  }
  apiError.value = tr('page.receipt.scanNotFound', {
    code: normalizeScanCode(raw) || raw,
  })
  focusHardwareScan()
  return false
}

function openScanner() {
  apiError.value = ''
  scannerOpen.value = true
}

function onScanned(value) {
  scannerOpen.value = false
  processScanCode(value)
}

function onHardwareScanEnter() {
  const value = hardwareScanValue.value
  hardwareScanValue.value = ''
  if (value.trim()) {
    processScanCode(value)
  }
  focusHardwareScan()
}

useHardwareBarcodeScanner({
  onScan: (code) => processScanCode(code),
  isActive: () => !modalOpen.value && !scannerOpen.value && !tableLoading.value,
})

function productIdsSignature(list) {
  if (!list?.length) return ''
  return list.map((p) => [p.id, p._syncStatus, p._stockQty].join(':')).join('|')
}

function applyRowsIfChanged(next) {
  if (!Array.isArray(next)) return false
  const nextSig = productIdsSignature(next)
  const curSig = productIdsSignature(rows.value)
  if (curSig && nextSig && curSig === nextSig) return false
  rows.value = sortProductsForDisplay(next)
  return true
}

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

function mergeCatalogRows(pList, cList, stockByProduct) {
  const catMap = Object.fromEntries((cList || []).map((c) => [c.id, c.name]))
  return (pList || []).map((p) => {
    const stock = stockByProduct[p.id]
    return {
      ...p,
      _categoryName: catMap[p.category] || '—',
      _stockQty: Number(stock?.quantity ?? 0),
      _stockLow: Boolean(stock?.is_low),
    }
  })
}

function withPendingReceiptStatus(list, pendingMap = {}) {
  return (list || []).map((row) => ({
    ...row,
    _syncStatus: Number(pendingMap[row.id] || 0) > 0 ? 'pending' : 'synced',
  }))
}

async function refreshPendingReceiptCount() {
  pendingReceiptCount.value = await countPendingStockReceipts()
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

async function loadReceiptFromCache() {
  await hydrateOrganizationStore(org)
  const { orgId, branchId } = await resolvePosIds(org)
  if (!orgId) return { hadCache: false, orgId: null, branchId: null }

  const bid = branchFilter.value ? Number(branchFilter.value) : branchId
  const cached = await loadCatalogFromIndexedDB(orgId, bid, {
    refreshFromApi: false,
    skipPrune: true,
  })
  if (!cached.hasCache && !cached.products?.length) {
    return { hadCache: false, orgId, branchId: bid }
  }

  const stockByProduct = {}
  for (const [pid, qty] of Object.entries(cached.stockMap || {})) {
    stockByProduct[pid] = { quantity: qty, is_low: false }
  }

  const merged = mergeCatalogRows(cached.products, cached.categories, stockByProduct)
  const pendingMap = await getPendingStockReceiptMap(bid)
  applyRowsIfChanged(withPendingReceiptStatus(merged, pendingMap))
  await refreshPendingReceiptCount()
  attachProductImagesOnce()
  return { hadCache: true, orgId, branchId: bid }
}

async function refreshReceiptFromApi() {
  apiError.value = ''
  await hydrateOrganizationStore(org)
  const { orgId, branchId } = await resolvePosIds(org)
  const branchIdForStock = branchFilter.value || org.currentBranchId || branchId

  const browserOffline = typeof navigator !== 'undefined' && !navigator.onLine
  if (browserOffline || isOfflineMode()) {
    await loadReceiptFromCache()
    markProductsDisplayed()
    return
  }

  try {
    const [pList, cList, stockData] = await Promise.all([
      productsApi.list(),
      categories.list(),
      branchIdForStock
        ? stockLevels.list({ branch: branchIdForStock })
        : Promise.resolve({ results: [], summary: {} }),
    ])

    markApiReachable()
    const stockByProduct = {}
    for (const row of stockData.results || []) {
      stockByProduct[row.product] = row
    }

    const merged = mergeCatalogRows(pList, cList, stockByProduct)
    const pendingMap = await getPendingStockReceiptMap(branchIdForStock)
    applyRowsIfChanged(withPendingReceiptStatus(merged, pendingMap))
    await refreshPendingReceiptCount()
    markProductsDisplayed()
    attachProductImagesOnce()
    // Offline refreshdan keyin ham rasmlar ko'rinsin: API rasmlarini IndexedDBga oldindan keshlaymiz.
    cacheProductImages(merged, { concurrency: 3 })
      .then(() => attachProductImagesOnce())
      .catch(() => {})

    if (orgId && branchIdForStock) {
      persistCatalogToIndexedDB(orgId, branchIdForStock, pList, cList, stockData).catch(() => {})
    }
  } catch (error) {
    console.warn('[receipt] yuklash:', error)
    const data = error?.response?.data
    const restored = await loadReceiptFromCache()
    if (!restored.hadCache) {
      apiError.value = data?.detail || tr('page.receipt.loadError')
    }
    await checkApiReachable()
    markProductsDisplayed()
  }
}

async function fetchData({ background = false } = {}) {
  if (fetchInFlight) return fetchInFlight

  fetchInFlight = (async () => {
    const cacheLoad = await loadReceiptFromCache()
    if (cacheLoad.hadCache) {
      markProductsDisplayed()
      if (typeof navigator !== 'undefined' && navigator.onLine) {
        refreshReceiptFromApi().catch(() => {})
      }
      return
    }

    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      markProductsDisplayed()
      return
    }

    if (!background && !hasDisplayedProducts.value && !rows.value.length) {
      setTableLoading(true)
    }

    await refreshReceiptFromApi()
  })().finally(() => {
    fetchInFlight = null
  })

  return fetchInFlight
}

function onSyncComplete() {
  if (fetchInFlight) return
  const now = Date.now()
  if (now - lastSyncRefreshAt < 4000) return
  lastSyncRefreshAt = now
  refreshReceiptFromApi().catch(() => {})
  refreshPendingReceiptCount().catch(() => {})
}

function openReceiptModal(row) {
  selectedProduct.value = row
  receiptForm.branch = branchFilter.value || String(org.currentBranchId || '')
  receiptForm.quantity = '1'
  receiptForm.unit_cost = String(row.cost_price ?? 0)
  receiptForm.note = ''
  apiError.value = ''
  successMsg.value = ''
  modalOpen.value = true
  nextTick(() => {
    qtyInputRef.value?.focus()
    qtyInputRef.value?.select?.()
  })
}

function closeModal() {
  modalOpen.value = false
  selectedProduct.value = null
  focusHardwareScan()
}

function getUnitLabel(product) {
  if (!product) return ''
  return unitOptions.value.find((u) => u.value === product.unit)?.label || product.unit || ''
}

async function submitReceipt() {
  apiError.value = ''
  successMsg.value = ''

  if (!selectedProduct.value) return
  if (!receiptForm.branch) {
    apiError.value = tr('page.receipt.branchRequired')
    return
  }
  if (Number(receiptForm.quantity) <= 0) {
    apiError.value = tr('page.receipt.qtyRequired')
    return
  }

  saving.value = true
  try {
    const payload = {
      branch: Number(receiptForm.branch),
      product: Number(selectedProduct.value.id),
      movement_type: 'in',
      quantity: receiptForm.quantity,
      unit_cost: receiptForm.unit_cost || 0,
      note: receiptForm.note.trim(),
    }
    if (isOfflineMode()) {
      const { orgId } = await resolvePosIds(org)
      await saveOfflineStockReceipt(orgId, payload)
      successMsg.value = tr('page.receipt.offlineSaved', { name: selectedProduct.value.name })
    } else {
      await stockMovements.create(payload)
      successMsg.value = tr('page.receipt.success', { name: selectedProduct.value.name })
    }
    closeModal()
    await fetchData()
    focusHardwareScan()
  } catch (error) {
    if (isNetworkError(error)) {
      try {
        const { orgId } = await resolvePosIds(org)
        await saveOfflineStockReceipt(orgId, {
          branch: Number(receiptForm.branch),
          product: Number(selectedProduct.value.id),
          quantity: receiptForm.quantity,
          unit_cost: receiptForm.unit_cost || 0,
          note: receiptForm.note.trim(),
        })
        successMsg.value = tr('page.receipt.offlineSaved', { name: selectedProduct.value.name })
        closeModal()
        await fetchData()
        focusHardwareScan()
        return
      } catch {
        /* fallthrough */
      }
    }
    const data = error?.response?.data
    apiError.value =
      data?.detail ||
      (typeof data === 'object' ? Object.values(data).flat().join(' ') : '') ||
      tr('page.receipt.saveError')
  } finally {
    saving.value = false
  }
}

function leaveReceipt() {
  if (auth.isSeller) {
    router.push(routeWithPosShell('/app/pos'))
    return
  }
  router.push('/app/inventory')
}

watch(
  () => org.currentBranchId,
  (id) => {
    if (id && !branchFilter.value) {
      branchFilter.value = String(id)
    }
  },
)

watch(branchFilter, () => {
  if (!branchFilterReady || !branchFilter.value) return
  if (hasDisplayedProducts.value || rows.value.length) {
    loadReceiptFromCache()
      .then((cacheLoad) => {
        if (cacheLoad.hadCache) markProductsDisplayed()
        refreshReceiptFromApi().catch(() => {})
      })
      .catch(() => refreshReceiptFromApi().catch(() => {}))
    return
  }
  fetchData().catch(() => {})
})

onMounted(async () => {
  if (org.currentBranchId) branchFilter.value = String(org.currentBranchId)
  branchFilterReady = true
  await fetchData()
  await refreshPendingReceiptCount()
  focusHardwareScan()

  let skipInitialConnectivity = true
  unsubscribeConnectivity = onConnectivityChange((offline) => {
    const skip = skipInitialConnectivity
    skipInitialConnectivity = false
    if (offline) {
      loadReceiptFromCache().then(() => markProductsDisplayed())
      return
    }
    if (skip) return
    if (hasDisplayedProducts.value || rows.value.length) {
      refreshReceiptFromApi().catch(() => {})
    } else {
      fetchData({ background: true }).catch(() => {})
    }
  })

  window.addEventListener('savdopro:sync-complete', onSyncComplete)
})

onUnmounted(() => {
  unsubscribeConnectivity?.()
  window.removeEventListener('savdopro:sync-complete', onSyncComplete)
})

watch(modalOpen, (open) => {
  if (!open) focusHardwareScan()
})

watch(scannerOpen, (open) => {
  if (!open) focusHardwareScan()
})
</script>

<template>
  <div class="products-view stock-receipt-view receipt-view">
    <PageHeader :title="tr('page.receipt.title')" :subtitle="tr('page.receipt.subtitle')">
      <template #actions>
        <button type="button" class="btn btn--ghost" @click="leaveReceipt">
          {{ auth.isSeller ? '← Kassa' : '← Qoldiqlarga' }}
        </button>
      </template>
    </PageHeader>

    <p v-if="successMsg" class="form-message form-message--success receipt-view__banner">
      {{ successMsg }}
    </p>
    <p v-if="pendingReceiptCount > 0" class="form-message form-message--info receipt-view__banner">
      {{ tr('page.receipt.offlineBanner', { n: pendingReceiptCount }) }}
    </p>
    <p v-if="apiError && !tableLoading && !modalOpen" class="form-message form-message--error receipt-view__banner">
      {{ apiError }}
    </p>

    <!-- Skaner aparat: ko‘rinmas fokus (USB/Bluetooth klaviatura rejimi) -->
    <input
      v-show="!modalOpen && !scannerOpen"
      ref="hardwareScanRef"
      v-model="hardwareScanValue"
      type="text"
      class="receipt-hardware-scan-sink"
      data-hardware-scan="1"
      autocomplete="off"
      tabindex="-1"
      aria-hidden="true"
      @keydown.enter.prevent="onHardwareScanEnter"
    />

    <div class="products-view__toolbar card">
      <select v-model="branchFilter" class="products-view__filter-select">
        <option value="" disabled>{{ tr('page.receipt.selectBranch') }}</option>
        <option v-for="b in org.branches" :key="b.id" :value="String(b.id)">
          {{ branchLabel(b) }}
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
      <button
        type="button"
        class="btn btn--ghost products-view__scan"
        :title="tr('page.receipt.scanTitle')"
        @click="openScanner"
      >
        <span aria-hidden="true">▣</span>
        {{ tr('page.products.btnScanner') }}
      </button>
    </div>

    <p class="receipt-view__hint">{{ tr('page.receipt.rowHint') }}</p>

    <div class="products-view__table card">
      <DataTable
        :columns="columns"
        :rows="filteredRows"
        :loading="tableLoading"
        clickable
        actions-label=""
        :empty-text="tr('page.receipt.emptyTable')"
        @row-click="openReceiptModal"
      >
        <template #cell:_syncStatus="{ row }">
          <SyncStatusIcon
            :kind="receiptSyncIconKind(row._syncStatus)"
            :label="syncStatusLabelMap[row._syncStatus] || row._syncStatus"
          />
        </template>
        <template #cell:image_url="{ row }">
          <div class="products-view__thumb-wrap">
            <img
              v-if="productRowHasImage(row)"
              class="products-view__thumb"
              :src="productRowImageSrc(row)"
              :alt="row.name || ''"
              loading="lazy"
              @error="onProductImageError(row)"
              @load="onProductImageLoad(row)"
            />
            <span v-else class="products-view__thumb--empty" aria-hidden="true">—</span>
          </div>
        </template>
        <template #cell:name="{ row }">
          <div class="products-view__name-cell">
            <span class="products-view__name-primary">{{ row.name || '—' }}</span>
            <span class="receipt-view__tap-hint">{{ tr('page.receipt.tapKirim') }}</span>
          </div>
        </template>
        <template #cell:_stockQty="{ row }">
          <span
            class="products-view__stock"
            :class="{ 'products-view__stock--low': row._stockLow }"
          >
            {{ branchFilter ? formatStockQty(row) : '—' }}
          </span>
        </template>
      </DataTable>
    </div>

    <AppModal
      :open="modalOpen"
      :title="selectedProduct ? tr('page.receipt.modalTitle', { name: selectedProduct.name }) : tr('page.receipt.title')"
      width="520px"
      @close="closeModal"
    >
      <form v-if="selectedProduct" class="receipt-modal-form" @submit.prevent="submitReceipt">
        <div class="receipt-modal-form__product card">
          <div class="receipt-modal-form__product-name">{{ selectedProduct.name }}</div>
          <div class="receipt-modal-form__meta">
            <span v-if="selectedProduct.sku">SKU: {{ selectedProduct.sku }}</span>
            <span>
              {{ tr('page.products.colStock') }}:
              {{ formatStockQty(selectedProduct) }}
            </span>
          </div>
        </div>

        <label class="field">
          <span>{{ tr('page.receipt.branchLabel') }} <i class="required">*</i></span>
          <select v-model="receiptForm.branch" required>
            <option value="" disabled>—</option>
            <option v-for="b in org.branches" :key="b.id" :value="String(b.id)">
              {{ branchLabel(b) }}
            </option>
          </select>
        </label>

        <div class="receipt-modal-form__row">
          <label class="field">
            <span>
              {{ tr('page.receipt.qtyLabel') }}
              <small>({{ getUnitLabel(selectedProduct) }})</small>
              <i class="required">*</i>
            </span>
            <input
              ref="qtyInputRef"
              v-model="receiptForm.quantity"
              type="number"
              min="0.001"
              step="0.001"
              required
            />
          </label>
          <label class="field">
            <span>{{ tr('page.receipt.costLabel') }}</span>
            <input v-model="receiptForm.unit_cost" type="number" min="0" step="0.01" />
          </label>
        </div>

        <div class="receipt-modal-form__total">
          <span>{{ tr('page.receipt.lineTotal') }}</span>
          <strong>
            {{ lineTotal.toLocaleString(numberLocale(), { maximumFractionDigits: 2 }) }} so‘m
          </strong>
        </div>

        <label class="field">
          <span>{{ tr('page.receipt.noteLabel') }}</span>
          <input
            v-model.trim="receiptForm.note"
            type="text"
            maxlength="255"
            :placeholder="tr('page.receipt.notePlaceholder')"
          />
        </label>

        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </form>

      <template #footer>
        <div class="receipt-modal-form__footer">
          <button type="button" class="btn btn--ghost" @click="closeModal">
            {{ tr('page.receipt.cancel') }}
          </button>
          <button
            type="button"
            class="btn btn--primary"
            :disabled="saving"
            @click="submitReceipt"
          >
            {{ saving ? tr('page.receipt.saving') : tr('page.receipt.save') }}
          </button>
        </div>
      </template>
    </AppModal>

    <MobileCameraScanFab label-key="page.receipt.scanCamera" @click="openScanner" />

    <BarcodeScanner
      :open="scannerOpen"
      :title="tr('page.receipt.scanTitle')"
      @close="scannerOpen = false"
      @scanned="onScanned"
    />
  </div>
</template>

<style scoped>
.receipt-view__banner {
  margin: 0 0 12px;
}

.receipt-hardware-scan-sink {
  position: fixed;
  left: -10000px;
  top: 0;
  width: 1px;
  height: 1px;
  opacity: 0;
  padding: 0;
  border: 0;
  margin: 0;
}

.receipt-view__hint {
  margin: 0 0 10px;
  font-size: 0.88rem;
  color: var(--text-muted);
}

.products-view__scan {
  flex-shrink: 0;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .products-view__toolbar .products-view__scan {
    display: none;
  }
}

.receipt-view__tap-hint {
  display: block;
  margin-top: 2px;
  font-size: 0.75rem;
  color: var(--accent);
  font-weight: 500;
}

.receipt-modal-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.receipt-modal-form__product {
  padding: 12px 14px;
  background: var(--surface-soft);
}

.receipt-modal-form__product-name {
  font-weight: 600;
  font-size: 1.05rem;
}

.receipt-modal-form__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
  margin-top: 6px;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.receipt-modal-form__row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.receipt-modal-form__total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-radius: var(--radius);
  background: var(--surface-soft);
  font-size: 0.95rem;
}

.receipt-modal-form__total strong {
  font-size: 1.1rem;
}

.receipt-modal-form__footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  width: 100%;
}

.products-view__thumb-wrap {
  width: 48px;
  height: 48px;
}

.products-view__thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 8px;
}

.products-view__thumb--empty {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: var(--surface-soft);
  color: var(--text-muted);
  font-size: 0.85rem;
}

.products-view__name-cell {
  min-width: 0;
}

.products-view__name-primary {
  display: block;
  font-weight: 500;
}

.products-view__stock {
  font-weight: 500;
}

.products-view__stock--low {
  color: var(--danger, #b1442b);
}

@media (max-width: 560px) {
  .receipt-modal-form__row {
    grid-template-columns: 1fr;
  }
}
</style>
