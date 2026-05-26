<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import AppModal from '../../components/AppModal.vue'
import BarcodeScanner from '../../components/BarcodeScanner.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import { useHardwareBarcodeScanner } from '../../composables/useHardwareBarcodeScanner'
import { findProductByScanCode, normalizeScanCode } from '../../lib/barcodeScan'
import { sortProductsForDisplay } from '../../lib/productSort'
import { attachCachedImagesToProducts, resolveProductImageSrc } from '../../offline/imageCache'
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
const loading = ref(true)
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

function numberLocale() {
  return locale.value === 'ru' ? 'ru-RU' : 'uz-UZ'
}

function productRowImageSrc(row) {
  return resolveProductImageSrc(row)
}

function productRowHasImage(row) {
  return Boolean(productRowImageSrc(row))
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
  isActive: () => !modalOpen.value && !scannerOpen.value && !loading.value,
})

async function fetchData() {
  loading.value = true
  apiError.value = ''
  try {
    const branchId = branchFilter.value || org.currentBranchId
    const [pList, cList, stockData] = await Promise.all([
      productsApi.list(),
      categories.list(),
      branchId
        ? stockLevels.list({ branch: branchId })
        : Promise.resolve({ results: [], summary: {} }),
    ])

    const catMap = Object.fromEntries((cList || []).map((c) => [c.id, c.name]))
    const stockByProduct = {}
    for (const row of stockData.results || []) {
      stockByProduct[row.product] = row
    }

    const merged = (pList || []).map((p) => {
      const stock = stockByProduct[p.id]
      return {
        ...p,
        _categoryName: catMap[p.category] || '—',
        _stockQty: Number(stock?.quantity ?? 0),
        _stockLow: Boolean(stock?.is_low),
      }
    })

    rows.value = sortProductsForDisplay(await attachCachedImagesToProducts(merged))
  } catch (error) {
    const data = error?.response?.data
    apiError.value = data?.detail || tr('page.receipt.loadError')
  } finally {
    loading.value = false
  }
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
    await stockMovements.create({
      branch: Number(receiptForm.branch),
      product: Number(selectedProduct.value.id),
      movement_type: 'in',
      quantity: receiptForm.quantity,
      unit_cost: receiptForm.unit_cost || 0,
      note: receiptForm.note.trim(),
    })
    successMsg.value = tr('page.receipt.success', { name: selectedProduct.value.name })
    closeModal()
    await fetchData()
    focusHardwareScan()
  } catch (error) {
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
  if (branchFilter.value) fetchData()
})

onMounted(async () => {
  if (org.currentBranchId) branchFilter.value = String(org.currentBranchId)
  await fetchData()
  focusHardwareScan()
})

watch(modalOpen, (open) => {
  if (!open) focusHardwareScan()
})

watch(scannerOpen, (open) => {
  if (!open) focusHardwareScan()
})
</script>

<template>
  <div class="products-view stock-receipt-view">
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
    <p v-if="apiError && !loading && !modalOpen" class="form-message form-message--error receipt-view__banner">
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
        :loading="loading"
        clickable
        actions-label=""
        :empty-text="tr('page.receipt.emptyTable')"
        @row-click="openReceiptModal"
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
