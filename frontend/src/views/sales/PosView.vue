<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import AppModal from '../../components/AppModal.vue'
import BrandLogo from '../../components/BrandLogo.vue'
import { formatQuantity } from '../../lib/formatQuantity'
import { localDateTimeIso } from '../../lib/localDateTime'
import { routeWithPosShell } from '../../posShellQuery'
import { debtors as debtorsApi } from '../../services/debtors.service'
import { sales } from '../../services/sales.service'
import { useAuthStore } from '../../stores/auth'
import { useOrganizationStore } from '../../stores/organization'
import { loadCatalogFromIndexedDB } from '../../offline/catalogSync'
import { loadDebtorsMerged, createOfflineDebtor, isLocalDebtorRef } from '../../offline/offlineDebtors'
import {
  hydrateOrganizationStore,
  resolveOfflineCashierName,
  resolvePosIds,
} from '../../offline/posContext'
import { scheduleFullSync } from '../../offline/syncScheduler'
import {
  checkApiReachable,
  isOfflineMode,
  isNetworkError,
  onConnectivityChange,
} from '../../offline/connectivity'
import { resolveProductImageSrc } from '../../offline/imageCache'
import { countPendingSales, newClientUuid, saveOfflineSale } from '../../offline/offlineSales'

const auth = useAuthStore()
const org = useOrganizationStore()

const productList = ref([])
const categoryList = ref([])
const stockMap = ref({})
const loading = ref(true)
const isOnline = ref(!isOfflineMode())
const catalogOffline = ref(false)
const pendingSalesCount = ref(0)
const search = ref('')
const selectedCategory = ref('')
const cartOpen = ref(false)
const paymentOpen = ref(false)
const submitting = ref(false)
const apiError = ref('')
const lastReceipt = ref(null)
const receiptOpen = ref(false)
const scanFlash = ref('')
const chipRowEl = ref(null)
/** `grid` — ixcham kataklar; `comfort` — kattaroq kartalar. */
const productLayout = ref('grid')

function scrollChips(direction) {
  const el = chipRowEl.value
  if (!el) return
  el.scrollBy({ left: direction * 180, behavior: 'smooth' })
}

function toggleProductLayout() {
  productLayout.value = productLayout.value === 'grid' ? 'comfort' : 'grid'
}

const UNIT_LABEL = {
  piece: 'dona',
  kg: 'kg',
  liter: 'litr',
  pack: 'paket',
}

const cart = reactive({
  items: [],
  discount: '0',
  note: '',
})

const payments = reactive({
  cashAmount: '',
  cardAmount: '',
})

/** To‘lov modali tablari (yonma-yon) */
const PAYMENT_TABS = [
  { code: 'cash', label: 'Naqd' },
  { code: 'card', label: 'Karta' },
  { code: 'mixed', label: 'Aralash' },
  { code: 'credit', label: 'Qarzga' },
]
const activeMethod = ref('cash')
/** Aralash ichida: naqd+karta yoki qarzga */
const mixedSubMode = ref(null)

const isCreditPayment = computed(
  () =>
    activeMethod.value === 'credit' ||
    (activeMethod.value === 'mixed' && mixedSubMode.value === 'credit'),
)

const showCreditDebtorUI = computed(() => isCreditPayment.value)

const submitDisabled = computed(
  () =>
    submitting.value ||
    total.value <= 0 ||
    (activeMethod.value === 'mixed' && !mixedSubMode.value) ||
    (!isCreditPayment.value && remaining.value > 0) ||
    (isCreditPayment.value && !hasDebtorSelected.value),
)

const submitDisabledHint = computed(() => {
  if (total.value <= 0) return 'Savatda mahsulot yo‘q.'
  if (activeMethod.value === 'mixed' && !mixedSubMode.value) {
    return '«Aralash» ichida «Aralash» yoki «Qarzga» ni tanlang.'
  }
  if (isCreditPayment.value && !hasDebtorSelected.value) {
    return 'Qarzdorni tanlang yoki «+ Yangi qarzdor» orqali kiriting.'
  }
  if (!isCreditPayment.value && remaining.value > 0) {
    return `To‘lov yetarli emas — yana ${formatMoney(remaining.value)} so‘m kerak.`
  }
  return ''
})

const debtorList = ref([])
const debtorsLoading = ref(false)
const selectedDebtorId = ref('')
const newDebtorMode = ref(false)
const newDebtor = reactive({ name: '', phone: '' })

const filteredProducts = computed(() => {
  const q = search.value.trim().toLowerCase()
  return productList.value.filter((p) => {
    if (selectedCategory.value && p.category !== Number(selectedCategory.value)) return false
    if (!q) return true
    return (
      p.name?.toLowerCase().includes(q) ||
      p.sku?.toLowerCase().includes(q) ||
      p.barcode?.toLowerCase().includes(q)
    )
  })
})

const subtotal = computed(() =>
  cart.items.reduce((sum, line) => sum + Number(line.quantity) * Number(line.unit_price), 0),
)

const discountNum = computed(() => Number(cart.discount || 0))
const total = computed(() => Math.max(0, subtotal.value - discountNum.value))

/** Savatdagi jami miqdor (referensdagi «umumiy miqdor»). */
const cartTotalQty = computed(() =>
  cart.items.reduce((sum, i) => sum + Number(i.quantity || 0), 0),
)

/** Tanlangan usul bo‘yicha jami to‘langan summa */
const totalPaid = computed(() => {
  const cash = Number(payments.cashAmount || 0)
  const card = Number(payments.cardAmount || 0)
  if (activeMethod.value === 'cash') return cash
  if (activeMethod.value === 'card') return card
  if (activeMethod.value === 'mixed' && mixedSubMode.value === 'split') return cash + card
  if (isCreditPayment.value) return cash + card
  return cash + card
})
const changeAmount = computed(() => Math.max(0, totalPaid.value - total.value))
const remaining = computed(() => Math.max(0, total.value - totalPaid.value))
const creditDebtAmount = computed(() => (isCreditPayment.value ? remaining.value : 0))
const hasDebtorSelected = computed(() => {
  if (newDebtorMode.value) return Boolean(newDebtor.name.trim())
  return Boolean(selectedDebtorId.value)
})


async function loadCatalogFromCache({ markOffline = null } = {}) {
  await hydrateOrganizationStore(org)
  const { orgId, branchId } = await resolvePosIds(org)
  if (!orgId) return false
  const cached = await loadCatalogFromIndexedDB(orgId, branchId)
  if (!cached.hasCache) {
    return productList.value.length > 0
  }
  productList.value = cached.products
  categoryList.value = cached.categories
  stockMap.value = cached.stockMap
  if (markOffline === true || (markOffline === null && isOfflineMode())) {
    catalogOffline.value = true
  } else if (markOffline === false) {
    catalogOffline.value = false
  }
  return true
}

async function refreshPendingCount() {
  pendingSalesCount.value = await countPendingSales()
}

function refreshOnlineState() {
  isOnline.value = !isOfflineMode()
}

async function fetchAll() {
  loading.value = true
  await hydrateOrganizationStore(org)
  const { orgId, branchId } = await resolvePosIds(org)
  refreshOnlineState()

  if (orgId) {
    await loadCatalogFromCache({ markOffline: true })
  }

  loading.value = false

  if (!orgId) {
    await refreshPendingCount()
    return
  }

  const ok = await checkApiReachable()
  refreshOnlineState()

  if (!ok) {
    catalogOffline.value = true
    await loadCatalogFromCache({ markOffline: true })
    await refreshPendingCount()
    return
  }

  if (branchId) {
    try {
      await scheduleFullSync(orgId, branchId, {
        branches: org.branches,
        organization: org.organization,
        force: true,
      })
      await loadCatalogFromCache({ markOffline: false })
    } catch {
      catalogOffline.value = true
      await loadCatalogFromCache({ markOffline: true })
    }
  }

  refreshOnlineState()
  await refreshPendingCount()
}

function stockOf(productId) {
  return stockMap.value[productId] ?? 0
}

/** Savatda ushbu mahsulot uchun jami miqdor (bazadagi qoldiq o‘zgarmaydi). */
function qtyInCartForProduct(productId) {
  let sum = 0
  for (const i of cart.items) {
    if (i.product === productId) sum += Number(i.quantity || 0)
  }
  return sum
}

/** Katakda ko‘rinadigan «yana sotish mumkin» qoldiq: ombor − savat. */
function displayStock(productId) {
  return Math.max(0, stockOf(productId) - qtyInCartForProduct(productId))
}

function flashScan(msg, ms = 2000) {
  scanFlash.value = msg
  setTimeout(() => {
    scanFlash.value = ''
  }, ms)
}

function addToCart(product) {
  const offline = isOfflineMode()
  const max = stockOf(product.id)
  if (!offline && max <= 0) {
    flashScan('Omborda qoldiq yo‘q')
    return false
  }
  const existing = cart.items.find((i) => i.product === product.id)
  if (existing) {
    const next = Number(existing.quantity) + 1
    if (!offline && next > max) {
      flashScan(`Omborda maksimum ${max} ${UNIT_LABEL[product.unit] || ''}`)
      return false
    }
    existing.quantity = String(next)
    return true
  }
  cart.items.push({
    product: product.id,
    name: product.name,
    unit: product.unit,
    image_url: resolveProductImageSrc(product) || product.image_url || '',
    quantity: '1',
    unit_price: String(product.sell_price ?? '0'),
  })
  return true
}

function changeQty(line, delta) {
  const offline = isOfflineMode()
  const max = stockOf(line.product)
  const next = Number(line.quantity) + delta
  if (next <= 0) {
    cart.items = cart.items.filter((i) => i !== line)
    return
  }
  if (!offline && next > max) {
    flashScan(`Omborda maksimum ${max} ${UNIT_LABEL[line.unit] || ''}`)
    return
  }
  line.quantity = String(next)
}

function onLineQuantityChange(line) {
  const max = stockOf(line.product)
  let n = Number(line.quantity)
  if (!Number.isFinite(n) || n <= 0) {
    cart.items = cart.items.filter((i) => i !== line)
    return
  }
  if (!isOfflineMode() && n > max) {
    line.quantity = String(max)
    flashScan(`Maksimum ${max} ${UNIT_LABEL[line.unit] || ''}`)
    return
  }
  line.quantity = String(n)
}

function removeLine(line) {
  cart.items = cart.items.filter((i) => i !== line)
}

function clearCart() {
  cart.items = []
  cart.discount = '0'
  cart.note = ''
}

async function fetchDebtors() {
  const { orgId } = await resolvePosIds(org)
  debtorsLoading.value = true
  try {
    if (isOfflineMode()) {
      debtorList.value = orgId ? await loadDebtorsMerged(orgId) : []
      return
    }
    debtorList.value = await debtorsApi.list()
    if (orgId) {
      const { syncDebtorsToIndexedDB } = await import('../../offline/fullSync')
      await syncDebtorsToIndexedDB(orgId).catch(() => {})
    }
  } catch {
    debtorList.value = orgId ? await loadDebtorsMerged(orgId) : []
  } finally {
    debtorsLoading.value = false
  }
}

function openPayment() {
  if (!cart.items.length) return
  apiError.value = ''
  payments.cashAmount = String(total.value)
  payments.cardAmount = ''
  activeMethod.value = 'cash'
  mixedSubMode.value = null
  selectedDebtorId.value = ''
  newDebtorMode.value = false
  newDebtor.name = ''
  newDebtor.phone = ''
  paymentOpen.value = true
  fetchDebtors()
}

/** Tab almashtirganda: bitta usulda ikkinchi maydon yig‘indiga qo‘shilmasin */
function setPaymentMethod(code) {
  if (code === 'cash') {
    mixedSubMode.value = null
    payments.cardAmount = ''
    if (!payments.cashAmount) payments.cashAmount = String(total.value)
  } else if (code === 'card') {
    mixedSubMode.value = null
    payments.cashAmount = ''
    if (!payments.cardAmount) payments.cardAmount = String(total.value)
  } else if (code === 'mixed') {
    if (activeMethod.value === 'mixed' && mixedSubMode.value) {
      mixedSubMode.value = null
      return
    }
    activeMethod.value = 'mixed'
    return
  } else if (code === 'credit') {
    mixedSubMode.value = null
    payments.cardAmount = ''
    payments.cashAmount = '0'
    activeMethod.value = 'credit'
    if (isOfflineMode() && !debtorList.value.length) newDebtorMode.value = true
    return
  }
  activeMethod.value = code
}

function setMixedSubMode(mode) {
  mixedSubMode.value = mode
  if (mode === 'split') {
    const cash = Number(payments.cashAmount || 0)
    const card = Number(payments.cardAmount || 0)
    if (!cash && !card) {
      payments.cashAmount = String(total.value)
      payments.cardAmount = '0'
    } else if (!payments.cardAmount && cash < total.value) {
      payments.cardAmount = String(Math.max(0, total.value - cash))
    }
  } else if (mode === 'credit') {
    payments.cardAmount = ''
    payments.cashAmount = '0'
    if (isOfflineMode() && !debtorList.value.length) newDebtorMode.value = true
  }
}

function setQuickCash(amount) {
  payments.cashAmount = String(amount)
  if (activeMethod.value === 'mixed' && mixedSubMode.value === 'split') syncMixedCardFromCash()
}

/** Aralash: kartaga qolgan summani yozish */
function syncMixedCardFromCash() {
  const cash = Number(payments.cashAmount || 0)
  payments.cardAmount = String(Math.max(0, total.value - cash))
}

function fillMixedCardRemainder() {
  syncMixedCardFromCash()
}

function fillMixedHalf() {
  const half = Math.ceil(total.value / 2)
  payments.cashAmount = String(half)
  payments.cardAmount = String(Math.max(0, total.value - half))
}

async function resolveDebtorForSale() {
  const { orgId } = await resolvePosIds(org)

  if (!newDebtorMode.value) {
    if (!selectedDebtorId.value) return {}
    const v = selectedDebtorId.value
    if (isLocalDebtorRef(v)) {
      const client_uuid = v.slice('local:'.length)
      const d = debtorList.value.find((x) => x._client_uuid === client_uuid)
      return {
        debtor_client_uuid: client_uuid,
        debtor_name: d?.name || '',
      }
    }
    const d = debtorList.value.find((x) => String(x.id) === String(v))
    return {
      debtor: Number(v),
      debtor_name: d?.name || '',
    }
  }

  if (isOfflineMode()) {
    const created = await createOfflineDebtor(orgId, {
      name: newDebtor.name.trim(),
      phone: newDebtor.phone.trim(),
    })
    return {
      debtor_client_uuid: created.client_uuid,
      debtor_name: created.name,
    }
  }

  const created = await debtorsApi.create({
    name: newDebtor.name.trim(),
    phone: newDebtor.phone.trim(),
  })
  return { debtor: created.id, debtor_name: created.name }
}

async function submitSale() {
  apiError.value = ''
  const { branchId: saleBranchId } = await resolvePosIds(org)
  if (!saleBranchId) {
    apiError.value = 'Filial tanlanmagan.'
    return
  }
  if (total.value <= 0) {
    apiError.value = 'Savatda mahsulot yo‘q.'
    return
  }
  const isCredit = isCreditPayment.value
  if (!isCredit && totalPaid.value < total.value) {
    apiError.value = 'To‘langan summa yetarli emas.'
    return
  }
  if (isCredit && !hasDebtorSelected.value) {
    apiError.value = 'Qarzdorni tanlang yoki yangisini kiriting.'
    return
  }
  if (totalPaid.value > total.value) {
    apiError.value = 'To‘langan summa savdo summasidan oshmasligi kerak.'
    return
  }

  const paymentLines = []
  const cash = Number(payments.cashAmount || 0)
  const card = Number(payments.cardAmount || 0)
  if (isCredit) {
    if (cash > 0) paymentLines.push({ method: 'cash', amount: payments.cashAmount })
    if (card > 0) paymentLines.push({ method: 'card', amount: payments.cardAmount })
  } else if (activeMethod.value === 'mixed' && mixedSubMode.value === 'split') {
    if (cash <= 0 && card <= 0) {
      apiError.value = 'Naqd yoki karta summasini kiriting.'
      return
    }
    if (cash > 0) paymentLines.push({ method: 'cash', amount: payments.cashAmount })
    if (card > 0) paymentLines.push({ method: 'card', amount: payments.cardAmount })
  } else if (activeMethod.value === 'cash' && cash > 0) {
    paymentLines.push({ method: 'cash', amount: payments.cashAmount })
  } else if (activeMethod.value === 'card' && card > 0) {
    paymentLines.push({ method: 'card', amount: payments.cardAmount })
  }

  if (!isCredit && paymentLines.length === 0) {
    paymentLines.push({ method: 'cash', amount: String(total.value) })
  }

  const saleItems = cart.items.map((i) => ({
    product: i.product,
    quantity: i.quantity,
    unit_price: i.unit_price,
    product_name: i.name,
  }))

  async function finishOfflineSale() {
    const client_uuid = newClientUuid()
    const branchRow = org.branches.find((b) => Number(b.id) === Number(saleBranchId))
    const cashier_name = await resolveOfflineCashierName(auth)
    const debtorFields = isCredit ? await resolveDebtorForSale() : {}
    const payload = {
      client_uuid,
      sold_at: localDateTimeIso(),
      allow_offline: true,
      branch: saleBranchId,
      branch_name: branchRow?.name || org.currentBranch?.name || '',
      cashier_name,
      discount: cart.discount || 0,
      note: cart.note,
      items: saleItems,
      payments: paymentLines,
      ...debtorFields,
    }
    const result = await saveOfflineSale(payload)
    lastReceipt.value = result
    paymentOpen.value = false
    cartOpen.value = false
    receiptOpen.value = true
    clearCart()
    refreshOnlineState()
    await loadCatalogFromCache()
    await refreshPendingCount()
  }

  if (isOfflineMode()) {
    submitting.value = true
    try {
      await finishOfflineSale()
    } catch (err) {
      console.error('[offline] savdo saqlash:', err)
      apiError.value = 'Offline savdoni saqlashda xatolik.'
    } finally {
      submitting.value = false
    }
    return
  }

  submitting.value = true
  try {
    const debtorFields = isCredit ? await resolveDebtorForSale() : {}
    const payload = {
      sold_at: localDateTimeIso(),
      branch: saleBranchId,
      discount: cart.discount || 0,
      note: cart.note,
      items: saleItems.map(({ product, quantity, unit_price }) => ({
        product,
        quantity,
        unit_price,
      })),
      payments: paymentLines,
    }
    Object.assign(payload, debtorFields)
    const result = await sales.create(payload)
    lastReceipt.value = result
    paymentOpen.value = false
    cartOpen.value = false
    receiptOpen.value = true
    clearCart()
    await loadCatalogFromCache()
    await refreshPendingCount()
  } catch (error) {
    if (!isCredit && isNetworkError(error)) {
      try {
        await finishOfflineSale()
        return
      } catch (offlineErr) {
        console.error('[offline] fallback saqlash:', offlineErr)
        apiError.value = 'Server ishlamayapti, offline saqlash ham muvaffaqiyatsiz.'
        return
      }
    }
    const data = error?.response?.data
    apiError.value =
      data?.detail ||
      (typeof data === 'object' ? Object.values(data || {})?.[0]?.toString() : '') ||
      'Savdo qilishda xatolik.'
  } finally {
    submitting.value = false
  }
}

function formatMoney(n) {
  return Number(n || 0).toLocaleString('uz-UZ', { maximumFractionDigits: 2 })
}

function productImageSrc(p) {
  if (!p) return ''
  if (p._cachedImageUrl) return p._cachedImageUrl
  return resolveProductImageSrc(p)
}

function productTileInitials(p) {
  const n = String(p?.name || '').trim()
  if (!n) return '?'
  return n.length === 1 ? n.toUpperCase() : n.slice(0, 2).toUpperCase()
}

/** Korzinka qatori — saqlangan yoki katalogdan rasm */
function cartLineImageSrc(line) {
  const catalogProduct = productList.value.find((p) => p.id === line?.product)
  if (catalogProduct) return productImageSrc(catalogProduct)
  if (line?.image_url) return line.image_url
  return ''
}

function printReceipt() {
  window.print()
}

function onKeydown(event) {
  if (event.key === 'F2') {
    event.preventDefault()
    openPayment()
  }
}

function onBrowserConnectivityChange() {
  checkApiReachable().then(async (ok) => {
    refreshOnlineState()
    await hydrateOrganizationStore(org)
    const { orgId, branchId } = await resolvePosIds(org)
    if (!ok) {
      await loadCatalogFromCache({ markOffline: true })
      return
    }
    if (orgId && branchId) {
      scheduleFullSync(orgId, branchId, {
        branches: org.branches,
        organization: org.organization,
        force: true,
      }).then(() => loadCatalogFromCache({ markOffline: false }))
    }
  })
}

async function onSavdoproConnectivity(offline) {
  refreshOnlineState()
  await hydrateOrganizationStore(org)
  if (offline) {
    await loadCatalogFromCache({ markOffline: true })
    return
  }
  const { orgId, branchId } = await resolvePosIds(org)
  if (orgId && branchId) {
    scheduleFullSync(orgId, branchId, {
      branches: org.branches,
      organization: org.organization,
      force: true,
    }).then(() => loadCatalogFromCache({ markOffline: false }))
  }
}

function onSyncComplete() {
  refreshPendingState()
}

async function refreshPendingState() {
  await refreshPendingCount()
  refreshOnlineState()
  await loadCatalogFromCache()
}

let unsubscribeConnectivity = null

watch(() => org.currentBranchId, async (branchId) => {
  const { orgId } = await resolvePosIds(org)
  if (!branchId || !orgId) return
  await loadCatalogFromCache({ markOffline: isOfflineMode() })
  scheduleFullSync(orgId, branchId, {
    branches: org.branches,
    organization: org.organization,
    force: true,
  })
    .then(() => loadCatalogFromCache({ markOffline: false }))
    .catch(() => {})
})

watch(
  () => org.organization?.id,
  (id) => {
    if (id) fetchAll()
  }
)

onMounted(async () => {
  const { hydrateAuthFromOfflineSnapshot } = await import('../../offline/posContext')
  await hydrateAuthFromOfflineSnapshot(auth)
  await hydrateOrganizationStore(org)
  await fetchAll()
  unsubscribeConnectivity = onConnectivityChange((offline) => {
    onSavdoproConnectivity(offline)
  })
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('online', onBrowserConnectivityChange)
  window.addEventListener('offline', onBrowserConnectivityChange)
  window.addEventListener('savdopro:sync-complete', onSyncComplete)
})

onUnmounted(() => {
  unsubscribeConnectivity?.()
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('online', onBrowserConnectivityChange)
  window.removeEventListener('offline', onBrowserConnectivityChange)
  window.removeEventListener('savdopro:sync-complete', onSyncComplete)
})
</script>

<template>
  <div class="pos-view">
    <header class="pos-topbar">
      <div class="pos-topbar__brand">
        <h1 class="pos-topbar__title">Kassa</h1>
      </div>
    </header>

    <div v-if="pendingSalesCount > 0" class="pos-offline-banner" role="status">
      {{ pendingSalesCount }} ta savdo sinxronlash kutilmoqda
    </div>

    <div class="pos-dashboard">
      <div class="pos-mid">
        <aside class="pos-cart" :class="{ 'is-open': cartOpen }">
          <header class="pos-cart__head">
            <h3 class="pos-cart__title">
              Korzinka
              <span class="pos-cart__badge">{{ cart.items.length }}</span>
            </h3>
            <button v-if="cartOpen" class="pos-icon-close" type="button" aria-label="Yopish" @click="cartOpen = false">
              ×
            </button>
          </header>

          <div v-if="cart.items.length === 0" class="pos-cart__empty">
            Mahsulot tanlang
          </div>

          <ul v-else class="pos-cart__list">
            <li v-for="line in cart.items" :key="line.product" class="pos-cart__line">
              <div class="pos-cart__thumb">
                <img
                  v-if="cartLineImageSrc(line)"
                  class="pos-cart__thumb-img"
                  :src="cartLineImageSrc(line)"
                  :alt="line.name"
                  loading="lazy"
                />
                <span v-else class="pos-cart__thumb-placeholder" aria-hidden="true">{{
                  productTileInitials(line)
                }}</span>
              </div>
              <div class="pos-cart__info">
                <strong>{{ line.name }}</strong>
                <small>{{ formatMoney(line.unit_price) }} × {{ formatQuantity(line.quantity) }} {{ UNIT_LABEL[line.unit] }}</small>
              </div>
              <div class="pos-cart__qty">
                <button type="button" @click="changeQty(line, -1)">−</button>
                <input
                  v-model="line.quantity"
                  type="number"
                  step="0.001"
                  min="0"
                  :max="isOfflineMode() ? undefined : stockOf(line.product)"
                  @change="onLineQuantityChange(line)"
                />
                <button type="button" @click="changeQty(line, 1)">+</button>
              </div>
              <div class="pos-cart__amount">
                {{ formatMoney(Number(line.quantity) * Number(line.unit_price)) }}
              </div>
              <button class="pos-line-remove" type="button" @click="removeLine(line)">×</button>
            </li>
          </ul>
        </aside>

        <section class="pos-catalog pos-panel">
          <Transition name="fade">
            <div v-if="scanFlash" class="scan-flash">{{ scanFlash }}</div>
          </Transition>

          <div class="pos-catalog-tools">
            <div class="pos-catalog-tools__top">
              <div class="pos-search-wrap pos-search-wrap--toolbar">
                <span class="pos-search-wrap__icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="7" />
                    <path d="M21 21l-4.3-4.3" />
                  </svg>
                </span>
                <input
                  v-model="search"
                  class="pos-search-field pos-search-field--inset"
                  type="search"
                  placeholder="Mahsulot qidirish..."
                />
              </div>
              <button
                type="button"
                class="pos-layout-toggle"
                :class="{ 'is-grid': productLayout === 'grid', 'is-comfort': productLayout === 'comfort' }"
                :title="productLayout === 'grid' ? 'Kattaroq kartalar' : 'Zich tarmoq'"
                @click="toggleProductLayout"
              >
                <svg
                  v-if="productLayout === 'grid'"
                  viewBox="0 0 24 24"
                  width="22"
                  height="22"
                  fill="currentColor"
                  aria-hidden="true"
                >
                  <rect x="3" y="3" width="7" height="7" rx="1.5" />
                  <rect x="14" y="3" width="7" height="7" rx="1.5" />
                  <rect x="3" y="14" width="7" height="7" rx="1.5" />
                  <rect x="14" y="14" width="7" height="7" rx="1.5" />
                </svg>
                <svg
                  v-else
                  viewBox="0 0 24 24"
                  width="22"
                  height="22"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  aria-hidden="true"
                >
                  <line x1="4" y1="7" x2="20" y2="7" />
                  <line x1="4" y1="12" x2="20" y2="12" />
                  <line x1="4" y1="17" x2="16" y2="17" />
                </svg>
              </button>
            </div>
          </div>

          <div v-if="!loading && categoryList.length" class="pos-chip-wrap">
            <button type="button" class="pos-chip-scroll" aria-label="Chapga" @click="scrollChips(-1)">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M15 6l-6 6 6 6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
            <div ref="chipRowEl" class="pos-chip-row">
              <button
                type="button"
                class="pos-chip"
                :class="{ 'is-active': selectedCategory === '' }"
                @click="selectedCategory = ''"
              >
                Barchasi
              </button>
              <button
                v-for="c in categoryList"
                :key="'chip-' + c.id"
                type="button"
                class="pos-chip"
                :class="{ 'is-active': String(selectedCategory) === String(c.id) }"
                @click="selectedCategory = String(c.id)"
              >
                {{ c.name }}
              </button>
            </div>
            <button type="button" class="pos-chip-scroll" aria-label="O‘ngga" @click="scrollChips(1)">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5">
                <path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
          </div>

          <div v-if="loading" class="pos-empty">Yuklanmoqda...</div>
          <div v-else-if="filteredProducts.length === 0" class="pos-empty pos-empty--inline">
            <span v-if="isOfflineMode()" class="pos-empty__msg">
              Offline katalog bo‘sh. Avval internet bilan kassani ochib sinxron qiling.
            </span>
            <span v-else class="pos-empty__msg">Mahsulot topilmadi.</span>
            <RouterLink class="pos-text-link pos-text-link--compact" :to="routeWithPosShell('/app/products')">
              Katalogga o‘tish
            </RouterLink>
          </div>
          <div
            v-else
            class="product-grid"
            :class="productLayout === 'comfort' ? 'product-grid--comfort' : 'product-grid--dense'"
          >
            <button
              v-for="p in filteredProducts"
              :key="p.id"
              type="button"
              class="product-tile"
              :class="{ 'product-tile--zero': displayStock(p.id) <= 0 }"
              @click="addToCart(p)"
            >
              <div class="product-tile__media">
                <img
                  v-if="productImageSrc(p)"
                  class="product-tile__img"
                  :src="productImageSrc(p)"
                  :alt="p.name"
                  loading="lazy"
                />
                <span v-else class="product-tile__placeholder" aria-hidden="true">{{
                  productTileInitials(p)
                }}</span>
              </div>
              <div class="product-tile__body">
                <span class="product-tile__name">{{ p.name }}</span>
                <div class="product-tile__price-row">
                  <span class="product-tile__price">{{ formatMoney(p.sell_price) }}</span>
                  <span class="product-tile__unit">so‘m</span>
                </div>
                <div class="product-tile__footer">
                  <span class="product-tile__stock">
                    {{ displayStock(p.id) }} {{ UNIT_LABEL[p.unit] || '' }}
                  </span>
                </div>
              </div>
            </button>
          </div>
        </section>

        <div class="pos-checkout-bar pos-panel">
          <label class="pos-cart__discount">
            <span>Chegirma (so‘m)</span>
            <input v-model="cart.discount" type="number" min="0" step="0.01" />
          </label>

          <div class="pos-summary-cards">
            <div class="pos-summary-card">
              <span class="pos-summary-card__label">Mahsulotlar</span>
              <strong class="pos-summary-card__val">{{ cart.items.length }}</strong>
            </div>
            <div class="pos-summary-card">
              <span class="pos-summary-card__label">Umumiy miqdor</span>
              <strong class="pos-summary-card__val">{{ formatQuantity(cartTotalQty) }}</strong>
            </div>
            <div class="pos-summary-card">
              <span class="pos-summary-card__label">Chegirma</span>
              <strong class="pos-summary-card__val">{{ formatMoney(discountNum) }}</strong>
            </div>
          </div>

          <div class="pos-totals">
            <div><span>Oraliq:</span><strong>{{ formatMoney(subtotal) }}</strong></div>
            <div class="pos-totals__final"><span>Jami to‘lov:</span><strong>{{ formatMoney(total) }} so‘m</strong></div>
          </div>

          <div class="pos-cart__actions">
            <button
              class="pos-btn pos-btn--ghost"
              type="button"
              :disabled="!cart.items.length"
              @click="clearCart"
            >
              Bekor
            </button>
            <button
              class="pos-btn pos-btn--primary pos-btn--lg"
              type="button"
              :disabled="!cart.items.length || submitting"
              @click="openPayment"
            >
              To‘lash (F2)
            </button>
          </div>
        </div>
      </div>
    </div>

    <button class="pos-cart-toggle" type="button" @click="cartOpen = true">
      Korzinka ({{ cart.items.length }}) · {{ formatMoney(total) }}
    </button>

    <AppModal
      :open="paymentOpen"
      title="To‘lov"
      width="520px"
      @close="paymentOpen = false"
    >
      <div class="payment-modal">
        <div class="payment-total">
          To‘lanishi kerak: <strong>{{ formatMoney(total) }} so‘m</strong>
        </div>

        <div class="payment-tabs">
          <button
            v-for="m in PAYMENT_TABS"
            :key="m.code"
            type="button"
            :class="['payment-tab', activeMethod === m.code ? 'is-active' : '']"
            @click="setPaymentMethod(m.code)"
          >
            {{ m.label }}
          </button>
        </div>

        <div v-if="activeMethod === 'cash'" class="payment-section">
          <label class="field field--full">
            <span>Naqd to‘lov</span>
            <input v-model="payments.cashAmount" type="number" min="0" step="0.01" />
          </label>
          <div class="quick-amounts">
            <button type="button" @click="setQuickCash(total)">Aniq</button>
            <button type="button" @click="setQuickCash(Math.ceil(total / 10000) * 10000)">
              {{ formatMoney(Math.ceil(total / 10000) * 10000) }}
            </button>
            <button type="button" @click="setQuickCash(Math.ceil(total / 50000) * 50000)">
              {{ formatMoney(Math.ceil(total / 50000) * 50000) }}
            </button>
            <button type="button" @click="setQuickCash(Math.ceil(total / 100000) * 100000)">
              {{ formatMoney(Math.ceil(total / 100000) * 100000) }}
            </button>
          </div>
        </div>

        <div v-else-if="activeMethod === 'card'" class="payment-section">
          <label class="field field--full">
            <span>Karta orqali</span>
            <input v-model="payments.cardAmount" type="number" min="0" step="0.01" />
          </label>
          <p class="hint">Karta orqali to‘lovni kassa apparatida o‘tkazing va summani kiriting.</p>
        </div>

        <template v-else-if="activeMethod === 'mixed'">
          <template v-if="!mixedSubMode">
            <p class="hint payment-mixed-pick-hint">To'lov turini tanlang:</p>
            <div class="payment-subtabs">
              <button type="button" class="payment-subtab" @click="setMixedSubMode('split')">
                Aralash
              </button>
              <button type="button" class="payment-subtab" @click="setMixedSubMode('credit')">
                Qarzga
              </button>
            </div>
          </template>

          <div
            v-else-if="mixedSubMode === 'split'"
            class="payment-section payment-section--mixed"
          >

          <div class="payment-mixed-grid">
            <label class="field field--full">
              <span>Naqd pul</span>
              <input
                v-model="payments.cashAmount"
                type="number"
                min="0"
                step="0.01"
              />
            </label>
            <label class="field field--full">
              <span>Plastik karta</span>
              <input v-model="payments.cardAmount" type="number" min="0" step="0.01" />
            </label>
          </div>
          <div class="payment-mixed-actions">
            <button type="button" class="btn btn--ghost btn--sm" @click="fillMixedHalf">
              50 / 50
            </button>
            <button type="button" class="btn btn--ghost btn--sm" @click="fillMixedCardRemainder">
              Qolganini kartaga
            </button>
          </div>
          <p class="hint">
            Naqd + karta jami <strong>{{ formatMoney(total) }}</strong> so‘m dan kam bo‘lmasligi kerak.
          </p>
          </div>
        </template>

        <div v-if="showCreditDebtorUI" class="payment-section payment-section--credit">
          <label class="field field--full">
            <span>Qarzdor</span>
            <select v-if="!newDebtorMode" v-model="selectedDebtorId" :disabled="debtorsLoading">
              <option value="">Tanlang...</option>
              <option v-for="d in debtorList" :key="d.id" :value="String(d.id)">
                {{ d.name }}{{ d.phone ? ` (${d.phone})` : '' }} — qarz: {{ formatMoney(d.balance_due) }}
              </option>
            </select>
          </label>
          <button type="button" class="btn btn--ghost btn--sm" @click="newDebtorMode = !newDebtorMode">
            {{ newDebtorMode ? "Ro'yxatdan tanlash" : '+ Yangi qarzdor' }}
          </button>
          <template v-if="newDebtorMode">
            <label class="field field--full"><span>Ism *</span><input v-model="newDebtor.name" type="text" /></label>
            <label class="field field--full"><span>Telefon</span><input v-model="newDebtor.phone" type="tel" /></label>
          </template>
          <label class="field field--full">
            <span>Hozir naqd (ixtiyoriy)</span>
            <input v-model="payments.cashAmount" type="number" min="0" step="0.01" />
          </label>
          <p class="hint">Qolgan <strong>{{ formatMoney(creditDebtAmount) }}</strong> so'm qarzdor hisobiga yoziladi.</p>
        </div>

        <div class="payment-summary">
          <template v-if="activeMethod === 'mixed' && mixedSubMode === 'split'">
            <div class="payment-summary__row">
              <span>Naqd:</span><strong>{{ formatMoney(payments.cashAmount) }}</strong>
            </div>
            <div class="payment-summary__row">
              <span>Karta:</span><strong>{{ formatMoney(payments.cardAmount) }}</strong>
            </div>
          </template>
          <div><span>Jami to‘langan:</span><strong>{{ formatMoney(totalPaid) }}</strong></div>
          <div v-if="isCreditPayment && creditDebtAmount > 0" class="is-warn">
            <span>Qarzga:</span><strong>{{ formatMoney(creditDebtAmount) }}</strong>
          </div>
          <div v-else :class="remaining > 0 ? 'is-warn' : 'is-ok'">
            <span>{{ remaining > 0 ? 'Yetishmaydi:' : 'Qaytim:' }}</span>
            <strong>{{ formatMoney(remaining > 0 ? remaining : changeAmount) }}</strong>
          </div>
        </div>

        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </div>

      <template #footer>
        <p v-if="submitDisabledHint && !submitting" class="hint payment-submit-hint">
          {{ submitDisabledHint }}
        </p>
        <button class="btn btn--ghost" type="button" @click="paymentOpen = false">Bekor</button>
        <button
          class="btn btn--primary"
          type="button"
          :disabled="submitDisabled"
          @click="submitSale"
        >
          {{ submitting ? 'Saqlanmoqda...' : 'Savdo qilish' }}
        </button>
      </template>
    </AppModal>

    <AppModal
      :open="receiptOpen"
      title="Chek"
      width="420px"
      @close="receiptOpen = false"
    >
      <div v-if="lastReceipt" class="receipt">
        <p v-if="lastReceipt.offline" class="receipt__offline-ok">
          Sotuv muvaffaqiyatli (Offline)
        </p>
        <div class="receipt__head">
          <BrandLogo variant="receipt" />
          <small>{{ new Date(lastReceipt.sold_at).toLocaleString('uz-UZ') }}</small>
          <small>Chek #{{ lastReceipt.id }}</small>
        </div>
        <ul class="receipt__items">
          <li v-for="item in lastReceipt.items" :key="item.id">
            <div>{{ item.product_name }}</div>
            <div class="receipt__line-detail">
              <span>{{ formatQuantity(item.quantity) }} × {{ formatMoney(item.unit_price) }}</span>
              <span>{{ formatMoney(item.line_total) }}</span>
            </div>
          </li>
        </ul>
        <div class="receipt__totals">
          <div><span>Subtotal:</span><strong>{{ formatMoney(lastReceipt.subtotal) }}</strong></div>
          <div v-if="Number(lastReceipt.discount) > 0">
            <span>Chegirma:</span><strong>-{{ formatMoney(lastReceipt.discount) }}</strong>
          </div>
          <div class="receipt__final"><span>Jami:</span><strong>{{ formatMoney(lastReceipt.total) }} so‘m</strong></div>
          <div><span>To‘langan:</span><strong>{{ formatMoney(lastReceipt.paid) }}</strong></div>
          <div v-if="Number(lastReceipt.change) > 0">
            <span>Qaytim:</span><strong>{{ formatMoney(lastReceipt.change) }}</strong>
          </div>
        </div>
      </div>

      <template #footer>
        <button class="btn btn--ghost" type="button" @click="printReceipt">Chop etish</button>
        <button class="btn btn--primary" type="button" @click="receiptOpen = false">Yopish</button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.pos-view {
  /* Yorug‘ kassa — asosiy ilova bilan uyg‘un */
  --pv-bg: #f1f5f9;
  --pv-panel: #ffffff;
  --pv-panel-inner: #f8fafc;
  --pv-line: #e2e8f0;
  --pv-text: #0f172a;
  --pv-muted: #64748b;
  --pv-accent: #2563eb;
  --pv-accent-dark: #1d4ed8;
  --pv-accent-glow: rgba(37, 99, 235, 0.2);
  --pv-red: #ef4444;
  --pv-red-dark: #dc2626;

  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  color: var(--pv-text);
}

.pos-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  padding: 4px 0 16px;
  border-bottom: 1px solid var(--pv-line);
  margin-bottom: 4px;
}

.pos-topbar__brand {
  display: flex;
  align-items: center;
  gap: 10px;
}

.pos-topbar__title {
  margin: 0;
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.pos-topbar__badge {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.25s ease, border-color 0.25s ease, color 0.25s ease, box-shadow 0.25s ease;
}

.pos-topbar__badge--online {
  background: #dcfce7;
  color: #15803d;
  border: 1px solid #86efac;
  box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.45);
  animation: pos-badge-pulse-online 2.4s ease-in-out infinite;
}

.pos-topbar__badge--offline {
  background: #fee2e2;
  color: #b91c1c;
  border: 1px solid #fca5a5;
  box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.5);
  animation: pos-badge-pulse-offline 1.4s ease-in-out infinite;
}

@keyframes pos-badge-pulse-online {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.35);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(34, 197, 94, 0);
  }
}

@keyframes pos-badge-pulse-offline {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.55);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(239, 68, 68, 0);
  }
}

.pos-offline-banner {
  margin: 0 0 10px;
  padding: 10px 14px;
  border-radius: 10px;
  background: #fef3c7;
  border: 1px solid #fcd34d;
  color: #92400e;
  font-size: 0.875rem;
  font-weight: 600;
  text-align: center;
}

.pos-dashboard {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
  flex: 1;
  min-height: 0;
}

.pos-panel {
  background: var(--pv-panel);
  border: 1px solid var(--pv-line);
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.pos-search-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 4px 4px 12px;
  background: var(--pv-panel-inner);
  border: 1px solid var(--pv-line);
  border-radius: 10px;
}

.pos-search-wrap__icon {
  color: var(--pv-muted);
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.pos-search-field--inset {
  border: 0;
  background: transparent;
  padding: 10px 8px;
  border-radius: 0;
}

.pos-search-field--inset:focus {
  box-shadow: none;
}

.pos-search-field {
  width: 100%;
  border: 1px solid var(--pv-line);
  background: var(--pv-panel-inner);
  border-radius: 10px;
  padding: 11px 14px;
  font-size: 0.94rem;
  color: var(--pv-text);
  outline: none;
}

.pos-search-field::placeholder {
  color: var(--pv-muted);
}

.pos-search-field:focus {
  border-color: var(--pv-accent);
  box-shadow: 0 0 0 3px var(--pv-accent-glow);
}

.pos-catalog-tools {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex-shrink: 0;
}

.pos-catalog-tools__top {
  display: flex;
  align-items: stretch;
  gap: 10px;
}

.pos-search-wrap--toolbar {
  flex: 1;
  min-width: 0;
  min-height: 48px;
}

.pos-layout-toggle {
  flex-shrink: 0;
  width: 48px;
  min-width: 48px;
  height: 48px;
  border-radius: 12px;
  border: 1px solid var(--pv-line);
  background: var(--pv-panel-inner);
  color: var(--pv-muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}

.pos-layout-toggle:hover {
  border-color: var(--pv-accent);
  color: var(--pv-text);
}

.pos-layout-toggle.is-grid {
  background: var(--pv-accent);
  border-color: var(--pv-accent);
  color: #fff;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25);
}

.pos-layout-toggle.is-comfort {
  background: var(--pv-panel-inner);
  border-color: var(--pv-line);
  color: var(--pv-text);
}

.pos-mid {
  display: grid;
  grid-template-columns: minmax(400px, min(760px, 56vw)) minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 16px;
  min-width: 0;
  min-height: 0;
  align-items: stretch;
}

.pos-catalog {
  grid-column: 2;
  grid-row: 1 / -1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  padding: 14px 14px 12px;
}

.pos-chip-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  min-height: 44px;
}

.pos-chip-scroll {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1px solid var(--pv-line);
  background: var(--pv-panel-inner);
  color: var(--pv-muted);
  cursor: pointer;
  display: grid;
  place-items: center;
  transition:
    background 0.12s ease,
    border-color 0.12s ease,
    color 0.12s ease;
}

.pos-chip-scroll:hover {
  border-color: var(--pv-accent);
  color: var(--pv-text);
}

.pos-chip-row {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 2px 8px;
  scrollbar-width: thin;
  flex: 1;
  min-width: 0;
  scroll-behavior: smooth;
  -webkit-mask-image: linear-gradient(to right, transparent, #000 10px, #000 calc(100% - 10px), transparent);
  mask-image: linear-gradient(to right, transparent, #000 10px, #000 calc(100% - 10px), transparent);
}

.pos-chip {
  flex-shrink: 0;
  border: 1px solid var(--pv-line);
  background: var(--pv-panel-inner);
  color: var(--pv-muted);
  font: inherit;
  font-size: 0.86rem;
  font-weight: 500;
  padding: 10px 18px;
  border-radius: 999px;
  cursor: pointer;
  transition:
    background 0.12s ease,
    border-color 0.12s ease,
    color 0.12s ease;
}

.pos-chip:hover {
  border-color: var(--pv-accent);
  color: var(--pv-text);
}

.pos-chip.is-active {
  background: var(--pv-accent);
  border-color: var(--pv-accent);
  color: #fff;
}

.scan-flash {
  background: linear-gradient(135deg, var(--pv-accent-dark) 0%, var(--pv-accent) 100%);
  color: #fff;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 0.9rem;
  text-align: center;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.35);
}

.product-grid {
  display: grid;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
  padding-bottom: 10px;
  align-content: start;
}

.product-grid--dense {
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: 12px;
}

.product-grid--comfort {
  grid-template-columns: repeat(auto-fill, minmax(176px, 1fr));
  gap: 14px;
}

.product-tile {
  background: var(--pv-panel);
  border: 1px solid var(--pv-line);
  border-radius: 16px;
  padding: 16px 16px 14px;
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.06s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 12px;
  min-height: 196px;
}

.product-tile:hover {
  border-color: rgba(37, 99, 235, 0.45);
  box-shadow: 0 6px 22px rgba(15, 23, 42, 0.08);
}

.product-tile:active {
  transform: scale(0.98);
}

.product-tile__media {
  flex: 1;
  min-height: 112px;
  max-height: 132px;
  aspect-ratio: 1;
  max-width: 100%;
  margin: 0 auto;
  width: 100%;
  border-radius: 12px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  display: grid;
  place-items: center;
  overflow: hidden;
}

.product-tile__img {
  width: 100%;
  height: 100%;
  max-height: 132px;
  object-fit: contain;
  padding: 8px;
}

.product-tile__placeholder {
  font-size: 1.65rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #64748b;
  user-select: none;
}

.product-tile__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 0;
  flex-shrink: 0;
}

.product-tile__name {
  font-weight: 600;
  color: var(--pv-text);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 0.94rem;
  line-height: 1.25;
  text-align: left;
}

.product-tile__price-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
}

.product-tile__price {
  color: var(--pv-accent-dark);
  font-weight: 700;
  font-size: 1.02rem;
}

.product-tile__unit {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--pv-muted);
}

.product-tile__footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 2px;
}

.product-tile__stock {
  font-size: 0.78rem;
  font-weight: 500;
  color: var(--pv-muted);
}

.product-tile--zero {
  opacity: 0.48;
}

.product-tile--zero .product-tile__stock {
  color: #fca5a5;
}

.pos-empty {
  background: var(--pv-panel-inner);
  border: 1px dashed var(--pv-line);
  border-radius: 14px;
  padding: 36px 24px;
  text-align: center;
  color: var(--pv-muted);
}

.pos-empty--inline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 14px 20px;
  min-height: 148px;
  padding: 32px 24px;
  text-align: left;
}

.pos-empty__msg {
  font-size: 0.95rem;
}

.pos-text-link {
  display: inline-block;
  margin-top: 12px;
  padding: 8px 16px;
  border-radius: 10px;
  font-weight: 600;
  font-size: 0.9rem;
  color: #fff;
  background: var(--pv-accent);
  text-decoration: none;
  transition: filter 0.12s ease;
}

.pos-text-link--compact {
  margin-top: 0;
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 0.92rem;
}

.pos-text-link:hover {
  filter: brightness(1.08);
  color: #fff;
}

.pos-cart {
  grid-column: 1;
  grid-row: 1;
  background: var(--pv-panel);
  border: 1px solid var(--pv-line);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
}

.pos-checkout-bar {
  grid-column: 1;
  grid-row: 2;
  gap: 12px;
  min-width: 0;
}

.pos-cart__head {
  padding: 10px 12px;
  border-bottom: 1px solid var(--pv-line);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.pos-cart__title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--pv-text);
}

.pos-cart__badge {
  font-size: 0.68rem;
  font-weight: 700;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--pv-accent);
  color: #fff;
}

.pos-icon-close {
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--pv-muted);
  font-size: 1.5rem;
  line-height: 1;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition:
    background 0.12s ease,
    color 0.12s ease;
}

.pos-icon-close:hover {
  background: var(--pv-panel-inner);
  color: var(--pv-text);
}

.pos-cart__empty {
  padding: 20px 12px;
  text-align: center;
  color: var(--pv-muted);
  font-size: 0.85rem;
}

.pos-cart__list {
  list-style: none;
  margin: 0;
  padding: 4px 6px;
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
  min-height: 0;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
}

.pos-cart__list::-webkit-scrollbar {
  width: 6px;
}

.pos-cart__list::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 4px;
}

.pos-cart__line {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto auto 26px;
  gap: 6px 8px;
  padding: 6px 4px;
  border-bottom: 1px solid var(--pv-line);
  align-items: center;
}

.pos-cart__thumb {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  border: 1px solid var(--pv-line);
  background: var(--pv-panel-inner);
  overflow: hidden;
  display: grid;
  place-items: center;
  flex-shrink: 0;
}

.pos-cart__thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.pos-cart__thumb-placeholder {
  font-size: 0.65rem;
  font-weight: 700;
  color: var(--pv-muted);
  letter-spacing: 0.02em;
  user-select: none;
}

.pos-cart__line:last-child {
  border-bottom: 0;
}

.pos-cart__info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.pos-cart__info strong {
  font-size: 0.82rem;
  font-weight: 600;
  line-height: 1.2;
  color: var(--pv-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pos-cart__info small {
  font-size: 0.7rem;
  line-height: 1.2;
  color: var(--pv-muted);
}

.pos-cart__qty {
  display: flex;
  align-items: center;
  gap: 0;
  border: 1px solid var(--pv-line);
  border-radius: 6px;
  background: var(--pv-panel-inner);
}

.pos-cart__qty button {
  width: 24px;
  height: 24px;
  border: 0;
  background: transparent;
  font-size: 0.9rem;
  line-height: 1;
  cursor: pointer;
  color: var(--pv-text);
}

.pos-cart__qty input {
  width: 40px;
  border: 0;
  background: transparent;
  text-align: center;
  font-size: 0.78rem;
  color: var(--pv-text);
  outline: none;
  padding: 2px 0;
}

.pos-cart__amount {
  font-weight: 600;
  font-size: 0.8rem;
  color: var(--pv-text);
  white-space: nowrap;
  min-width: 4.5rem;
  text-align: right;
}

.pos-line-remove {
  width: 26px;
  height: 26px;
  border: 0;
  border-radius: 6px;
  background: var(--pv-panel-inner);
  color: var(--pv-muted);
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  transition:
    background 0.12s ease,
    color 0.12s ease;
}

.pos-line-remove:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #b91c1c;
}

.pos-summary-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.pos-summary-card {
  background: var(--pv-panel);
  border: 1px solid var(--pv-line);
  border-radius: 10px;
  padding: 10px 8px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pos-summary-card__label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--pv-muted);
}

.pos-summary-card__val {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--pv-text);
}

.pos-cart__discount {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  font-size: 0.88rem;
  color: var(--pv-muted);
}

.pos-cart__discount input {
  width: 120px;
  border: 1px solid var(--pv-line);
  border-radius: 10px;
  padding: 6px 10px;
  text-align: right;
  background: var(--pv-panel);
  color: var(--pv-text);
}

.pos-totals {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.88rem;
}

.pos-totals > div {
  display: flex;
  justify-content: space-between;
  color: var(--pv-muted);
}

.pos-totals__final {
  font-size: 1.05rem;
  color: var(--pv-text) !important;
  padding-top: 6px;
  border-top: 1px solid var(--pv-line);
}

.pos-totals__final strong {
  color: var(--pv-accent);
  font-size: 1.25rem;
}

.pos-cart__actions {
  display: flex;
  gap: 8px;
}

.pos-btn {
  border: 0;
  border-radius: 10px;
  padding: 12px 16px;
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
  transition:
    filter 0.12s ease,
    transform 0.08s ease,
    opacity 0.12s ease;
  flex: 1;
}

.pos-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.pos-btn:active:not(:disabled) {
  transform: scale(0.99);
}

.pos-btn--primary {
  background: linear-gradient(180deg, #60a5fa 0%, var(--pv-accent-dark) 100%);
  color: #fff;
}

.pos-btn--primary:hover:not(:disabled) {
  filter: brightness(1.06);
}

.pos-btn--ghost {
  background: var(--pv-panel);
  border: 1px solid var(--pv-line);
  color: var(--pv-muted);
}

.pos-btn--ghost:hover:not(:disabled) {
  border-color: var(--pv-accent);
  color: var(--pv-text);
}

.pos-btn--lg {
  padding: 14px 18px;
  font-size: 1rem;
}

.pos-cart-toggle {
  display: none;
}

.payment-modal {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.payment-total {
  background: #e5efff;
  color: #205a9a;
  padding: 14px;
  border-radius: var(--radius-sm);
  text-align: center;
  font-size: 0.98rem;
}

.payment-total strong {
  font-size: 1.4rem;
  display: block;
  margin-top: 4px;
  color: #1a3f73;
}

.payment-tabs {
  display: flex;
  gap: 8px;
}

.payment-tab {
  flex: 1;
  padding: 10px;
  border: 1px solid var(--line);
  background: var(--surface);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.92rem;
}

.payment-tab.is-active {
  background: #205a9a;
  border-color: #205a9a;
  color: #fff;
}

.payment-mixed-pick-hint {
  margin: 0 0 4px;
  text-align: center;
}

.payment-submit-hint {
  flex: 1 1 100%;
  margin: 0 0 8px;
  color: var(--warn, #b45309);
  font-size: 0.88rem;
}

.payment-subtabs {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
}

.payment-subtab {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid var(--line);
  background: var(--surface-soft, #f8fafc);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 0.92rem;
  font-weight: 500;
  color: var(--text-muted, #64748b);
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.payment-subtab.is-active {
  background: #205a9a;
  border-color: #205a9a;
  color: #fff;
}

.payment-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.payment-section--credit {
  gap: 12px;
}

.payment-mixed-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.payment-mixed-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.payment-summary__row {
  display: flex;
  justify-content: space-between;
  font-size: 0.88rem;
  color: var(--text-muted);
}

.payment-summary__row strong {
  color: var(--text);
}

.quick-amounts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
}

.quick-amounts button {
  padding: 10px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
  font-size: 0.86rem;
  cursor: pointer;
}

.quick-amounts button:hover {
  background: #e5efff;
  border-color: #7ea4e6;
}

.payment-summary {
  background: var(--surface-soft);
  padding: 12px;
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.payment-summary > div {
  display: flex;
  justify-content: space-between;
  font-size: 0.92rem;
}

.payment-summary .is-warn strong {
  color: #b1442b;
}

.payment-summary .is-ok strong {
  color: #2c7a3d;
}

.hint {
  font-size: 0.84rem;
  color: var(--text-muted);
}

.receipt {
  font-family: 'Courier New', monospace;
  padding: 10px;
}

.receipt__offline-ok {
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: #dcfce7;
  border: 1px solid #86efac;
  color: #166534;
  font-family: system-ui, sans-serif;
  font-size: 0.95rem;
  font-weight: 700;
  text-align: center;
}

.receipt__head {
  display: flex;
  flex-direction: column;
  align-items: center;
  border-bottom: 1px dashed var(--text-muted);
  padding-bottom: 10px;
  margin-bottom: 10px;
}

.receipt__items {
  list-style: none;
  padding: 0;
  margin: 0 0 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.receipt__line-detail {
  display: flex;
  justify-content: space-between;
  color: var(--text-muted);
  font-size: 0.88rem;
}

.receipt__totals {
  border-top: 1px dashed var(--text-muted);
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.receipt__totals > div {
  display: flex;
  justify-content: space-between;
  font-size: 0.92rem;
}

.receipt__final {
  font-size: 1.05rem;
  border-top: 1px dashed var(--text-muted);
  padding-top: 6px;
  margin-top: 6px;
}

@media (max-width: 980px) {
  .pos-dashboard {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .pos-mid {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
  }

  .pos-catalog,
  .pos-cart,
  .pos-checkout-bar {
    grid-column: auto;
    grid-row: auto;
  }

  .product-grid {
    max-height: none;
  }

  .pos-cart {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    max-width: min(560px, 96vw);
    max-height: 100vh;
    border-radius: 0;
    z-index: 50;
    transform: translateX(100%);
    transition: transform 0.2s ease;
    box-shadow: -8px 0 32px rgba(15, 23, 42, 0.12);
  }

  .pos-cart.is-open {
    transform: translateX(0);
  }

  .pos-cart-toggle {
    display: block;
    position: fixed;
    right: 16px;
    bottom: 16px;
    background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%);
    color: #fff;
    border: 0;
    padding: 14px 18px;
    border-radius: 999px;
    cursor: pointer;
    font-size: 0.92rem;
    font-weight: 500;
    z-index: 30;
    box-shadow: 0 8px 24px rgba(31, 111, 235, 0.45);
  }
}

@media (max-width: 480px) {
  .product-grid--dense,
  .product-grid--comfort {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .quick-amounts {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
