<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppModal from '../../components/AppModal.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import SyncStatusIcon from '../../components/SyncStatusIcon.vue'
import { POS_SHELL_QUERY_KEY, POS_SHELL_QUERY_VALUE } from '../../posShellQuery'
import {
  checkApiReachable,
  isOfflineMode,
  markApiReachable,
  onConnectivityChange,
} from '../../offline/connectivity'
import { createOfflineDebtor, loadDebtorsMerged } from '../../offline/offlineDebtors'
import {
  countPendingDebtorSyncItems,
  saveOfflineDebtPayment,
} from '../../offline/offlineDebtPayments'
import { countPendingSales } from '../../offline/offlineSales'
import { runPendingOfflineSync } from '../../offline/syncScheduler'
import { debtors as debtorsApi } from '../../services/debtors.service'
import { hydrateOrganizationStore, resolvePosIds } from '../../offline/posContext'
import { useApiNotify } from '../../composables/useApiNotify'
import { numberLocaleForUi, useI18n } from '../../i18n'
import { useOrganizationStore } from '../../stores/organization'

const route = useRoute()
const org = useOrganizationStore()
const { tr, locale } = useI18n()
const { showApiError } = useApiNotify()

const isPosMode = computed(() => {
  const q = route.query[POS_SHELL_QUERY_KEY]
  return q === POS_SHELL_QUERY_VALUE || q === 'true'
})

const rows = ref([])
const pendingSyncCount = ref(0)
const loading = ref(false)
const hasDisplayedDebtors = ref(false)
let fetchInFlight = null
let unsubscribeConnectivity = null

const tableLoading = computed(() => loading.value && filteredRows.value.length === 0)
const search = ref('')
const createOpen = ref(false)
const editOpen = ref(false)
const payOpen = ref(false)
const saving = ref(false)
const apiError = ref('')
const selected = ref(null)
const editingId = ref(null)

const createForm = reactive({
  name: '',
  phone: '',
  note: '',
  due_date: '',
})

const editForm = reactive({
  name: '',
  phone: '',
  note: '',
  due_date: '',
})

const payForm = reactive({
  amount: '',
  method: 'cash',
  note: '',
})

const dateLocale = computed(() => numberLocaleForUi(locale.value))

const syncStatusLabelMap = computed(() => ({
  pending: tr('page.debtors.sync.pending'),
  synced: tr('page.debtors.sync.synced'),
}))

function debtorSyncIconKind(status) {
  return status === 'pending' ? 'pending' : 'synced'
}

const columns = computed(() => [
  { key: '_syncStatus', label: tr('page.debtors.colSync'), width: '52px' },
  { key: 'name', label: tr('page.debtors.colName'), width: isPosMode.value ? '160px' : '180px' },
  { key: 'first_credit_at', label: tr('page.debtors.colTakenAt'), width: '110px' },
  { key: 'total_credit', label: tr('page.debtors.colTotal'), width: '110px' },
  { key: 'total_paid', label: tr('page.debtors.colPaid'), width: '110px' },
  { key: 'balance_due', label: tr('page.debtors.colRemaining'), width: '110px' },
  { key: 'due_date', label: tr('page.debtors.colDueDate'), width: '100px' },
  ...(isPosMode.value ? [] : [{ key: 'note', label: tr('page.debtors.colNote'), width: '120px' }]),
])

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter(
    (r) =>
      r.name?.toLowerCase().includes(q) ||
      r.phone?.toLowerCase().includes(q) ||
      r.note?.toLowerCase().includes(q),
  )
})

const totalDebt = computed(() =>
  rows.value.reduce((sum, r) => sum + Number(r.balance_due || 0), 0),
)

function numberLocale() {
  return numberLocaleForUi(locale.value)
}

function formatMoney(n) {
  const num = Number(n || 0).toLocaleString(numberLocale(), { maximumFractionDigits: 0 })
  return `${num} ${tr('page.billing.currencySom')}`
}

function formatDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString(dateLocale.value)
}

function formatDateTime(v) {
  if (!v) return '—'
  return new Date(v).toLocaleString(dateLocale.value, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function isOverdue(row) {
  if (!row.due_date || !Number(row.balance_due)) return false
  const due = new Date(row.due_date)
  due.setHours(23, 59, 59, 999)
  return due < new Date()
}

const payModalTitle = computed(() => {
  void locale.value
  if (!selected.value) return tr('page.debtors.payTitle')
  return tr('page.debtors.payTitleNamed', { name: selected.value.name || '—' })
})

function debtorsListSignature(list) {
  if (!list?.length) return ''
  return list
    .map((d) =>
      [
        d.id,
        d.balance_due,
        d.total_paid,
        d.total_credit,
        d._syncStatus,
        d._offlinePending ? 1 : 0,
      ].join(':'),
    )
    .join('|')
}

function applyDebtorsListIfChanged(next) {
  if (!Array.isArray(next)) return false
  const nextSig = debtorsListSignature(next)
  const curSig = debtorsListSignature(rows.value)
  if (curSig && nextSig && curSig === nextSig) return false
  rows.value = next
  return true
}

/** Offline to‘lov/yaratishdan keyin jadvalni majburan yangilash */
function setDebtorsRows(next) {
  if (!Array.isArray(next)) return
  rows.value = next
}

function setTableLoading(active) {
  if (active && hasDisplayedDebtors.value) return
  loading.value = active
}

function markDebtorsDisplayed() {
  loading.value = false
  if (rows.value.length > 0) {
    hasDisplayedDebtors.value = true
  }
}

async function refreshPendingSyncCount() {
  const [debtorItems, sales] = await Promise.all([
    countPendingDebtorSyncItems(),
    countPendingSales(),
  ])
  pendingSyncCount.value = debtorItems + sales
}

async function syncPendingNow() {
  if (isOfflineMode()) return
  try {
    await runPendingOfflineSync()
    await onSyncComplete()
  } catch (err) {
    console.warn('[debtors] sinxronlash:', err)
  }
}

async function loadDebtorsFromCache() {
  await hydrateOrganizationStore(org)
  const { orgId } = await resolvePosIds(org)
  if (!orgId) return { hadCache: false, orgId: null }

  const merged = await loadDebtorsMerged(orgId)
  await refreshPendingSyncCount()
  if (!merged.length) return { hadCache: false, orgId }

  applyDebtorsListIfChanged(merged)
  return { hadCache: true, orgId }
}

async function refreshDebtorsFromApi() {
  await hydrateOrganizationStore(org)
  const { orgId } = await resolvePosIds(org)

  const browserOffline = typeof navigator !== 'undefined' && !navigator.onLine
  if (browserOffline || isOfflineMode()) {
    if (orgId) {
      setDebtorsRows(await loadDebtorsMerged(orgId))
    }
    await refreshPendingSyncCount()
    markDebtorsDisplayed()
    return
  }

  try {
    const params = {}
    if (!isPosMode.value && search.value.trim()) params.q = search.value.trim()
    await debtorsApi.list(params)
    markApiReachable()

    if (orgId) {
      const { syncDebtorsToIndexedDB } = await import('../../offline/fullSync')
      await syncDebtorsToIndexedDB(orgId)
      setDebtorsRows(await loadDebtorsMerged(orgId))
    }

    await refreshPendingSyncCount()
    markDebtorsDisplayed()
  } catch (err) {
    console.warn('[debtors] yuklash:', err)
    if (orgId) {
      setDebtorsRows(await loadDebtorsMerged(orgId))
    }
    await checkApiReachable()
    await refreshPendingSyncCount()
    markDebtorsDisplayed()
  }
}

async function fetchDebtors({ background = false } = {}) {
  if (fetchInFlight) return fetchInFlight

  fetchInFlight = (async () => {
    const cacheLoad = await loadDebtorsFromCache()
    if (cacheLoad.hadCache) {
      markDebtorsDisplayed()
      if (typeof navigator !== 'undefined' && navigator.onLine) {
        refreshDebtorsFromApi().catch(() => {})
      }
      return
    }

    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      markDebtorsDisplayed()
      return
    }

    if (!background && !hasDisplayedDebtors.value && !rows.value.length) {
      setTableLoading(true)
    }

    await refreshDebtorsFromApi()
  })().finally(() => {
    fetchInFlight = null
  })

  return fetchInFlight
}

async function onSyncComplete() {
  await hydrateOrganizationStore(org)
  const { orgId } = await resolvePosIds(org)
  if (!orgId) return

  try {
    if (!isOfflineMode()) {
      const { syncDebtorsToIndexedDB } = await import('../../offline/fullSync')
      await syncDebtorsToIndexedDB(orgId)
    }
    setDebtorsRows(await loadDebtorsMerged(orgId))
    await refreshPendingSyncCount()
    markDebtorsDisplayed()
  } catch (err) {
    console.warn('[debtors] sinxron tugagach yangilash:', err)
    refreshDebtorsFromApi().catch(() => {})
  }
}

function resetCreateForm() {
  createForm.name = ''
  createForm.phone = ''
  createForm.note = ''
  createForm.due_date = ''
}

function openCreate() {
  apiError.value = ''
  resetCreateForm()
  createOpen.value = true
}

function toApiDate(v) {
  const s = String(v || '').trim()
  return s || null
}

async function submitCreate() {
  apiError.value = ''
  if (!createForm.name.trim()) {
    apiError.value = tr('page.debtors.errNameRequired')
    return
  }
  saving.value = true
  try {
    const { orgId } = await resolvePosIds(org)
    const payload = {
      name: createForm.name.trim(),
      phone: createForm.phone.trim(),
      note: createForm.note.trim(),
      due_date: toApiDate(createForm.due_date),
    }
    if (isOfflineMode()) {
      await createOfflineDebtor(orgId, payload)
      setDebtorsRows(await loadDebtorsMerged(orgId))
      await refreshPendingSyncCount()
    } else {
      await debtorsApi.create(payload)
      await fetchDebtors()
    }
    createOpen.value = false
  } catch (error) {
    apiError.value = error?.response?.data?.name?.[0] || error?.response?.data?.detail || tr('page.debtors.errSaveFailed')
  } finally {
    saving.value = false
  }
}

function openEdit(row) {
  editingId.value = row.id
  apiError.value = ''
  editForm.name = row.name || ''
  editForm.phone = row.phone || ''
  editForm.note = row.note || ''
  editForm.due_date = row.due_date || ''
  editOpen.value = true
}

async function submitEdit() {
  apiError.value = ''
  if (!editForm.name.trim()) {
    apiError.value = tr('page.debtors.errNameRequired')
    return
  }
  saving.value = true
  try {
    const updated = await debtorsApi.update(editingId.value, {
      name: editForm.name.trim(),
      phone: editForm.phone.trim(),
      note: editForm.note.trim(),
      due_date: toApiDate(editForm.due_date),
    })
    const idx = rows.value.findIndex((r) => r.id === editingId.value)
    if (idx >= 0) rows.value[idx] = updated
    editOpen.value = false
  } catch (error) {
    apiError.value = error?.response?.data?.name?.[0] || error?.response?.data?.detail || tr('page.debtors.errUpdateFailed')
  } finally {
    saving.value = false
  }
}

async function removeDebtor(row) {
  if (!confirm(tr('page.debtors.deleteConfirm', { name: row.name }))) return
  try {
    await debtorsApi.remove(row.id)
    rows.value = rows.value.filter((r) => r.id !== row.id)
  } catch (error) {
    showApiError(error, 'page.debtors.deleteFail')
  }
}

function openPay(row) {
  selected.value = row
  apiError.value = ''
  payForm.amount = Number(row.balance_due) > 0 ? String(row.balance_due) : ''
  payForm.method = 'cash'
  payForm.note = ''
  payOpen.value = true
}

function fillFullPay() {
  if (!selected.value) return
  payForm.amount = String(selected.value.balance_due)
}

async function submitPay() {
  apiError.value = ''
  if (!selected.value) return
  if (!org.currentBranchId) {
    apiError.value = tr('page.debtors.errNoBranch')
    return
  }
  const amount = Number(payForm.amount || 0)
  if (amount <= 0) {
    apiError.value = tr('page.debtors.errAmountPositive')
    return
  }
  if (amount > Number(selected.value.balance_due)) {
    apiError.value = tr('page.debtors.errAmountOver')
    return
  }
  saving.value = true
  try {
    const { orgId } = await resolvePosIds(org)
    const paymentPayload = {
      branch: org.currentBranchId,
      amount: payForm.amount,
      method: payForm.method,
      note: payForm.note,
    }

    if (isOfflineMode()) {
      if (!orgId) {
        apiError.value = tr('page.debtors.errNoBranch')
        return
      }
      await saveOfflineDebtPayment(orgId, selected.value, paymentPayload)
      setDebtorsRows(await loadDebtorsMerged(orgId))
      await refreshPendingSyncCount()
    } else {
      const result = await debtorsApi.pay(selected.value.id, paymentPayload)
      const idx = rows.value.findIndex((r) => r.id === selected.value.id)
      if (idx >= 0 && result.debtor) rows.value[idx] = result.debtor
    }
    payOpen.value = false
  } catch (error) {
    const data = error?.response?.data
    apiError.value =
      error?.message ||
      data?.amount?.[0] ||
      data?.detail ||
      (isOfflineMode() ? tr('page.debtors.errPayOffline') : tr('page.debtors.errPayFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await fetchDebtors()
  await refreshPendingSyncCount()
  if (!isOfflineMode() && pendingSyncCount.value > 0) {
    syncPendingNow().catch(() => {})
  }

  let skipInitialConnectivity = true
  unsubscribeConnectivity = onConnectivityChange((offline) => {
    const skip = skipInitialConnectivity
    skipInitialConnectivity = false
    if (offline) {
      loadDebtorsFromCache().then(() => markDebtorsDisplayed())
      return
    }
    if (skip) return
    refreshDebtorsFromApi().catch(() => {})
    if (pendingSyncCount.value > 0) {
      syncPendingNow().catch(() => {})
    }
  })

  window.addEventListener('savdopro:sync-complete', onSyncComplete)
})

onUnmounted(() => {
  unsubscribeConnectivity?.()
  window.removeEventListener('savdopro:sync-complete', onSyncComplete)
})
</script>

<template>
  <div class="products-view debtors-view" :class="{ 'debtors-view--pos': isPosMode }">
    <PageHeader
      v-if="!isPosMode"
      :title="tr('page.debtors.title')"
      :subtitle="tr('page.debtors.subtitle')"
    >
      <template #actions>
        <button class="btn btn--primary" type="button" @click="openCreate">{{ tr('page.debtors.addBtn') }}</button>
      </template>
    </PageHeader>

    <header v-else class="debtors-pos-head">
      <div>
        <h1 class="debtors-pos-head__title">{{ tr('page.debtors.posTitle') }}</h1>
        <p class="debtors-pos-head__sub">{{ tr('page.debtors.posSub') }}</p>
      </div>
      <button class="debtors-pos-head__add" type="button" @click="openCreate">{{ tr('page.debtors.posAddBtn') }}</button>
    </header>

    <div class="products-view__toolbar card debtors-toolbar">
      <div class="debtors-toolbar__stat">
        <span class="debtors-summary__label">{{ tr('page.debtors.summaryTotal') }}</span>
        <strong class="debtors-summary__value">{{ formatMoney(totalDebt) }}</strong>
      </div>
      <div class="products-view__search-wrap debtors-toolbar__search">
        <span class="products-view__search-icon" aria-hidden="true">⌕</span>
        <input
          v-model="search"
          type="search"
          class="products-view__search"
          :placeholder="tr('page.debtors.searchPlaceholder')"
          @keyup.enter="!isPosMode && fetchDebtors()"
        />
      </div>
      <button
        v-if="!isPosMode"
        class="btn btn--ghost btn--sm"
        type="button"
        @click="fetchDebtors"
      >
        {{ tr('page.debtors.searchBtn') }}
      </button>
    </div>

    <div class="products-view__table card">
      <DataTable
        :columns="columns"
        :rows="filteredRows"
        :loading="tableLoading"
        :actions-label="tr('page.debtors.colActions')"
        :empty-text="isPosMode ? tr('page.debtors.posEmpty') : tr('page.debtors.empty')"
      >
        <template #cell:_syncStatus="{ row }">
          <SyncStatusIcon
            :kind="debtorSyncIconKind(row._syncStatus)"
            :label="syncStatusLabelMap[row._syncStatus] || row._syncStatus"
          />
        </template>
        <template #cell:name="{ row }">
          <div class="debtor-name-cell">
            <strong>{{ row.name }}</strong>
            <small v-if="row.phone">{{ row.phone }}</small>
          </div>
        </template>
        <template #cell:first_credit_at="{ row }">
          <span class="debtors-date">{{ formatDateTime(row.first_credit_at) }}</span>
        </template>
        <template #cell:total_credit="{ row }">
          <span class="debtors-muted">{{ formatMoney(row.total_credit) }}</span>
        </template>
        <template #cell:total_paid="{ row }">
          <span class="debtors-paid">{{ formatMoney(row.total_paid) }}</span>
        </template>
        <template #cell:balance_due="{ row }">
          <strong :class="Number(row.balance_due) > 0 ? 'debt-amount' : 'debt-zero'">
            {{ formatMoney(row.balance_due) }}
          </strong>
        </template>
        <template #cell:due_date="{ row }">
          <span :class="['debtors-date', isOverdue(row) ? 'debtors-date--overdue' : '']">
            {{ formatDate(row.due_date) }}
          </span>
        </template>
        <template #cell:note="{ value }">
          <span class="debtors-muted">{{ value || '—' }}</span>
        </template>
        <template #actions="{ row }">
          <button
            class="btn btn--sm"
            :class="isPosMode ? 'btn--success' : 'icon-btn'"
            type="button"
            :disabled="!Number(row.balance_due)"
            @click="openPay(row)"
          >
            {{ isPosMode ? tr('page.debtors.posPayBtn') : tr('page.debtors.payDebt') }}
          </button>
          <template v-if="!isPosMode">
            <button class="icon-btn" type="button" @click="openEdit(row)">{{ tr('page.categories.edit') }}</button>
            <button class="icon-btn icon-btn--danger" type="button" @click="removeDebtor(row)">
              {{ tr('page.categories.delete') }}
            </button>
          </template>
        </template>
      </DataTable>
    </div>

    <AppModal
      :open="createOpen"
      :title="tr('page.debtors.createModalTitle')"
      :width="isPosMode ? '480px' : '440px'"
      @close="createOpen = false"
    >
      <div class="form-stack">
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldName') }}</span>
          <input v-model="createForm.name" type="text" autocomplete="name" />
        </label>
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldPhone') }}</span>
          <input v-model="createForm.phone" type="tel" autocomplete="tel" />
        </label>
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldDueDate') }}</span>
          <input v-model="createForm.due_date" type="date" />
        </label>
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldNote') }}</span>
          <input v-model="createForm.note" type="text" />
        </label>
        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </div>
      <template #footer>
        <button class="btn btn--ghost" type="button" @click="createOpen = false">{{ tr('page.debtors.cancel') }}</button>
        <button class="btn btn--primary" type="button" :disabled="saving" @click="submitCreate">
          {{ saving ? tr('page.debtors.saving') : tr('page.debtors.save') }}
        </button>
      </template>
    </AppModal>

    <AppModal :open="editOpen" :title="tr('page.debtors.editModalTitle')" width="440px" @close="editOpen = false">
      <div class="form-stack">
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldName') }}</span>
          <input v-model="editForm.name" type="text" />
        </label>
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldPhone') }}</span>
          <input v-model="editForm.phone" type="tel" />
        </label>
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldDueDate') }}</span>
          <input v-model="editForm.due_date" type="date" />
        </label>
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldNote') }}</span>
          <input v-model="editForm.note" type="text" />
        </label>
        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </div>
      <template #footer>
        <button class="btn btn--ghost" type="button" @click="editOpen = false">{{ tr('page.debtors.cancel') }}</button>
        <button class="btn btn--primary" type="button" :disabled="saving" @click="submitEdit">
          {{ saving ? tr('page.debtors.saving') : tr('page.debtors.update') }}
        </button>
      </template>
    </AppModal>

    <AppModal
      :open="payOpen"
      :title="payModalTitle"
      :width="isPosMode ? '480px' : '440px'"
      @close="payOpen = false"
    >
      <div v-if="selected" class="form-stack">
        <p class="pay-balance">
          {{ tr('page.debtors.currentDebt') }} <strong>{{ formatMoney(selected.balance_due) }}</strong>
        </p>
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldAmount') }}</span>
          <input v-model="payForm.amount" type="number" min="0" step="0.01" />
        </label>
        <div class="quick-amounts">
          <button type="button" @click="fillFullPay">{{ tr('page.debtors.fillFull') }}</button>
        </div>
        <label class="field field--full">
          <span>{{ tr('page.debtors.payMethod') }}</span>
          <select v-model="payForm.method">
            <option value="cash">{{ tr('page.debtors.methodCash') }}</option>
            <option value="card">{{ tr('page.debtors.methodCard') }}</option>
            <option value="transfer">{{ tr('page.debtors.methodTransfer') }}</option>
          </select>
        </label>
        <label class="field field--full">
          <span>{{ tr('page.debtors.fieldNote') }}</span>
          <input v-model="payForm.note" type="text" />
        </label>
        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </div>
      <template #footer>
        <button class="btn btn--ghost" type="button" @click="payOpen = false">{{ tr('page.debtors.cancel') }}</button>
        <button class="btn btn--primary" type="button" :disabled="saving" @click="submitPay">
          {{ saving ? tr('page.debtors.saving') : tr('page.debtors.save') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.debtors-toolbar__stat {
  flex-shrink: 0;
}

.debtors-toolbar__search {
  flex: 1;
  min-width: 200px;
  max-width: 480px;
  margin-left: auto;
}

.debtors-summary__label {
  display: block;
  font-size: 0.85rem;
  color: var(--text-muted, #64748b);
  margin-bottom: 4px;
}

.debtors-summary__value {
  font-size: 1.35rem;
  color: var(--danger, #c0392b);
}

.debtors-pos-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.debtors-pos-head__title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.debtors-pos-head__sub {
  margin: 4px 0 0;
  font-size: 0.9rem;
  color: #64748b;
}

.debtors-pos-head__add {
  flex-shrink: 0;
  border: 0;
  border-radius: 12px;
  padding: 12px 18px;
  font-size: 0.95rem;
  font-weight: 600;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.28);
}

.debtors-view--pos .products-view__table .data-table {
  font-size: 0.88rem;
}

.debtors-view--pos .products-view__table .data-table th,
.debtors-view--pos .products-view__table .data-table td {
  padding: 10px 12px;
  white-space: nowrap;
}

.debtors-view--pos .products-view__table .data-table__actions-col {
  min-width: 120px;
}

.debtors-view .products-view__table {
  overflow-x: auto;
}

.debtor-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.debtor-name-cell strong {
  font-weight: 600;
}

.debtor-name-cell small {
  font-size: 0.8rem;
  color: var(--text-muted, #64748b);
}

@media (max-width: 640px) {
  .debtors-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .debtors-toolbar__search {
    min-width: 0;
    max-width: none;
    margin-left: 0;
    width: 100%;
  }

  .debtors-toolbar__stat {
    width: 100%;
    text-align: center;
  }

  .debtors-pos-head {
    flex-direction: column;
    align-items: stretch;
  }

  .debtors-pos-head__add {
    width: 100%;
  }

  .debtors-view--pos .products-view__table .data-table th,
  .debtors-view--pos .products-view__table .data-table td {
    white-space: normal;
  }
}

.debtors-date {
  font-size: 0.85rem;
  color: var(--text-muted, #64748b);
}

.debtors-date--overdue {
  color: var(--danger, #dc2626);
  font-weight: 600;
}

.debtors-muted {
  color: var(--text-muted, #64748b);
  font-size: 0.9rem;
}

.debtors-paid {
  color: #16a34a;
  font-size: 0.9rem;
}

.debt-amount {
  color: var(--danger, #c0392b);
}

.debt-zero {
  color: var(--text-muted, #64748b);
}

.btn--success {
  background: #16a34a;
  color: #fff;
  border: 0;
}

.btn--success:disabled {
  background: #e2e8f0;
  color: #94a3b8;
}

.pay-balance {
  margin: 0 0 8px;
  font-size: 0.95rem;
}

.quick-amounts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: -4px 0 8px;
}

.quick-amounts button {
  border: 1px solid var(--line);
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
  padding: 6px 12px;
  cursor: pointer;
  font-size: 0.88rem;
}

.debtors-page--pos .quick-amounts button {
  padding: 10px 16px;
  font-size: 0.95rem;
  border-radius: 10px;
}

.form-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.debtors-view--pos :deep(.field input),
.debtors-view--pos :deep(.field select) {
  font-size: 1rem;
  padding: 12px 14px;
}
</style>
