<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'

import AppModal from '../../components/AppModal.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import SaleReceipt from '../../components/SaleReceipt.vue'
import SyncStatusIcon from '../../components/SyncStatusIcon.vue'
import { formatQuantity } from '../../lib/formatQuantity'
import { isOfflineMode } from '../../offline/connectivity'
import { hydrateOrganizationStore, resolvePosIds } from '../../offline/posContext'
import { loadSalesFromIndexedDB } from '../../offline/salesCache'
import { sales as salesApi } from '../../services/sales.service'
import { numberLocaleForUi, useI18n } from '../../i18n'
import { useOrganizationStore } from '../../stores/organization'

const org = useOrganizationStore()
const { tr, locale, branchLabel, branchName } = useI18n()

const rows = ref([])
const loading = ref(true)
const detailOpen = ref(false)
const detail = ref(null)
const receiptOpen = ref(false)
const receiptSale = ref(null)
const receiptLoading = ref(false)

const filters = reactive({
  branch: '',
  status: '',
  date_from: '',
  date_to: '',
})

const statusLabelMap = computed(() => ({
  completed: tr('page.salesHistory.status.completed'),
  canceled: tr('page.salesHistory.status.canceled'),
  returned: tr('page.salesHistory.status.returned'),
  pending: tr('page.salesHistory.status.pending'),
}))

const statusFilterOptions = computed(() =>
  ['completed', 'canceled', 'returned', 'pending'].map((code) => ({
    code,
    label: statusLabelMap.value[code],
  })),
)

function saleStatusIconKind(status) {
  if (status === 'completed') return 'synced'
  if (status === 'canceled') return 'canceled'
  if (status === 'returned') return 'returned'
  if (status === 'pending') return 'pending'
  return 'pending'
}

const columns = computed(() => {
  const loc = numberLocaleForUi(locale.value)
  return [
    {
      key: 'sold_at',
      label: tr('page.salesHistory.colTime'),
      formatter: (v) => (v ? new Date(v).toLocaleString(loc, { hour12: false }) : '—'),
      width: '160px',
    },
    { key: 'id', label: tr('page.salesHistory.colReceiptNo'), width: '80px' },
    {
      key: 'branch_name',
      label: tr('page.salesHistory.colBranch'),
      formatter: (v) => branchName(v, org.branches),
      width: '140px',
    },
    {
      key: 'cashier_name',
      label: tr('page.salesHistory.colCashier'),
      formatter: (v) => v || '—',
      width: '140px',
    },
    {
      key: 'debtor_name',
      label: tr('page.salesHistory.colDebtor'),
      formatter: (v) => v || '—',
      width: '140px',
    },
    { key: 'status', label: tr('page.salesHistory.colStatus'), width: '72px' },
    { key: 'total', label: tr('page.salesHistory.colAmount'), width: '120px' },
  ]
})

const detailModalTitle = computed(() => {
  void locale.value
  if (!detail.value) return tr('page.salesHistory.receiptLabel')
  return tr('page.salesHistory.detailTitle', { id: detail.value.id })
})

function formatMoney(n) {
  const num = Number(n || 0).toLocaleString(numberLocaleForUi(locale.value), {
    maximumFractionDigits: 0,
  })
  return `${num} ${tr('page.billing.currencySom')}`
}

function paymentMethodLabel(method) {
  if (method === 'cash') return tr('page.salesHistory.payCash')
  if (method === 'card') return tr('page.salesHistory.payCard')
  if (method === 'mixed') return tr('pos.payTab.mixed')
  if (method === 'transfer') return tr('page.debtors.methodTransfer')
  return method || '—'
}

async function fetchSales() {
  loading.value = true
  await hydrateOrganizationStore(org)
  const { orgId, branchId } = await resolvePosIds(org)

  try {
    if (isOfflineMode()) {
      rows.value = await loadSalesFromIndexedDB(orgId, {
        branchId: filters.branch || branchId,
      })
      if (filters.status) {
        rows.value = rows.value.filter((r) => r.status === filters.status)
      }
      return
    }

    const params = {}
    if (filters.branch) params.branch = filters.branch
    if (filters.status) params.status = filters.status
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to
    rows.value = await salesApi.list(params)
    if (orgId) {
      const { syncSalesToIndexedDB } = await import('../../offline/salesCache')
      syncSalesToIndexedDB(orgId).catch(() => {})
    }
  } catch {
    if (orgId) {
      rows.value = await loadSalesFromIndexedDB(orgId, {
        branchId: filters.branch || branchId,
      })
    } else {
      rows.value = []
    }
  } finally {
    loading.value = false
  }
}

async function showDetail(row) {
  if (row._offlinePending) {
    detail.value = {
      ...row,
      items: row.items || [],
      payments: [],
    }
    detailOpen.value = true
    return
  }
  detail.value = await salesApi.retrieve(row.id)
  detailOpen.value = true
}

async function openReceipt(row) {
  receiptLoading.value = true
  try {
    if (row.items?.length) {
      receiptSale.value = row
    } else {
      receiptSale.value = await salesApi.retrieve(row.id)
    }
    receiptOpen.value = true
  } finally {
    receiptLoading.value = false
  }
}

function reprintFromDetail() {
  if (!detail.value) return
  receiptSale.value = detail.value
  receiptOpen.value = true
}

function printReceipt() {
  window.print()
}

function clearFilters() {
  filters.branch = ''
  filters.status = ''
  filters.date_from = ''
  filters.date_to = ''
}

watch(filters, fetchSales, { deep: true })

onMounted(async () => {
  await hydrateOrganizationStore(org)
  const { branchId } = await resolvePosIds(org)
  if (branchId) filters.branch = String(branchId)
  await fetchSales()
  window.addEventListener('savdopro:sync-complete', fetchSales)
})

onUnmounted(() => {
  window.removeEventListener('savdopro:sync-complete', fetchSales)
})
</script>

<template>
  <div class="products-view sales-history-view">
    <PageHeader :title="tr('page.salesHistory.title')" :subtitle="tr('page.salesHistory.subtitle')" />

    <div class="products-view__toolbar card">
      <select v-model="filters.branch" class="products-view__filter-select">
        <option value="">{{ tr('page.movements.filterAllBranches') }}</option>
        <option v-for="b in org.branches" :key="b.id" :value="b.id">{{ branchLabel(b) }}</option>
      </select>

      <select v-model="filters.status" class="products-view__filter-select">
        <option value="">{{ tr('page.salesHistory.filterAllStatuses') }}</option>
        <option v-for="opt in statusFilterOptions" :key="opt.code" :value="opt.code">{{ opt.label }}</option>
      </select>

      <input v-model="filters.date_from" type="date" class="products-view__filter-input" />
      <input v-model="filters.date_to" type="date" class="products-view__filter-input" />

      <button class="btn btn--ghost btn--sm" type="button" @click="clearFilters">
        {{ tr('page.salesHistory.clearFilters') }}
      </button>
    </div>

    <div class="products-view__table card">
      <DataTable
        :columns="columns"
        :rows="rows"
        :loading="loading"
        clickable
        :empty-text="tr('page.salesHistory.emptyTable')"
        @row-click="showDetail"
      >
      <template #cell:status="{ row }">
        <SyncStatusIcon
          :kind="saleStatusIconKind(row.status)"
          :label="statusLabelMap[row.status] || row.status"
        />
      </template>
      <template #cell:total="{ row }">
        <strong>{{ formatMoney(row.total) }}</strong>
      </template>
      <template #actions="{ row }">
        <button class="icon-btn" type="button" @click.stop="openReceipt(row)">{{ tr('page.salesHistory.btnPrint') }}</button>
        <button class="icon-btn" type="button" @click.stop="showDetail(row)">{{ tr('page.salesHistory.btnView') }}</button>
      </template>
      </DataTable>
    </div>

    <AppModal
      :open="detailOpen"
      :title="detailModalTitle"
      width="520px"
      @close="detailOpen = false"
    >
      <div v-if="detail" class="sale-detail">
        <div class="sale-detail__meta">
          <div><span>{{ tr('page.salesHistory.metaTime') }}</span><strong>{{ new Date(detail.sold_at).toLocaleString(numberLocaleForUi(locale)) }}</strong></div>
          <div><span>{{ tr('page.salesHistory.metaBranch') }}</span><strong>{{ branchName(detail.branch_name, org.branches) }}</strong></div>
          <div><span>{{ tr('page.salesHistory.metaCashier') }}</span><strong>{{ detail.cashier_name || '—' }}</strong></div>
          <div v-if="detail.debtor_name">
            <span>{{ tr('page.salesHistory.metaDebtor') }}</span><strong>{{ detail.debtor_name }}</strong>
          </div>
          <div><span>{{ tr('page.salesHistory.metaStatus') }}</span><strong>{{ statusLabelMap[detail.status] || detail.status }}</strong></div>
        </div>

        <h4>{{ tr('page.salesHistory.sectionProducts') }}</h4>
        <ul class="sale-detail__items">
          <li v-for="item in detail.items" :key="item.id">
            <div>
              <strong>{{ item.product_name }}</strong>
              <small>{{ formatQuantity(item.quantity) }} × {{ formatMoney(item.unit_price) }}</small>
            </div>
            <strong>{{ formatMoney(item.line_total) }}</strong>
          </li>
        </ul>

        <h4>{{ tr('page.salesHistory.sectionPayment') }}</h4>
        <ul class="sale-detail__items">
          <li v-for="p in detail.payments" :key="p.id">
            <div><strong>{{ paymentMethodLabel(p.method) }}</strong></div>
            <strong>{{ formatMoney(p.amount) }}</strong>
          </li>
        </ul>

        <div class="sale-detail__totals">
          <div><span>{{ tr('pos.receiptSubtotal') }}</span><strong>{{ formatMoney(detail.subtotal) }}</strong></div>
          <div v-if="Number(detail.discount) > 0">
            <span>{{ tr('pos.receiptDiscount') }}</span><strong>-{{ formatMoney(detail.discount) }}</strong>
          </div>
          <div class="sale-detail__final">
            <span>{{ tr('pos.receiptTotal') }}</span><strong>{{ formatMoney(detail.total) }}</strong>
          </div>
          <div><span>{{ tr('pos.receiptPaid') }}</span><strong>{{ formatMoney(detail.paid) }}</strong></div>
          <div v-if="Number(detail.balance_due) > 0" class="sale-detail__debt">
            <span>{{ tr('pos.summaryCredit') }}</span><strong>{{ formatMoney(detail.balance_due) }}</strong>
          </div>
          <div v-if="Number(detail.change) > 0">
            <span>{{ tr('pos.receiptChange') }}</span><strong>{{ formatMoney(detail.change) }}</strong>
          </div>
        </div>
      </div>

      <template #footer>
        <button class="btn btn--ghost" type="button" @click="reprintFromDetail">{{ tr('page.salesHistory.reprint') }}</button>
        <button class="btn btn--primary" type="button" @click="detailOpen = false">{{ tr('pos.closeBtn') }}</button>
      </template>
    </AppModal>

    <AppModal
      :open="receiptOpen"
      :title="tr('page.salesHistory.receiptModalTitle')"
      width="420px"
      @close="receiptOpen = false"
    >
      <div v-if="receiptLoading" class="sales-history__receipt-loading">{{ tr('app.boot.loading') }}</div>
      <SaleReceipt v-else-if="receiptSale" :sale="receiptSale" />

      <template #footer>
        <button class="btn btn--ghost" type="button" @click="printReceipt">{{ tr('page.salesHistory.btnPrint') }}</button>
        <button class="btn btn--primary" type="button" @click="receiptOpen = false">{{ tr('pos.closeBtn') }}</button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.sale-detail h4 {
  margin: 16px 0 8px;
  font-size: 0.92rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.sale-detail__meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
}

.sale-detail__meta > div {
  display: flex;
  flex-direction: column;
  font-size: 0.86rem;
}

.sale-detail__meta span {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.sale-detail__items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.sale-detail__items li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--surface-soft);
  font-size: 0.92rem;
}

.sale-detail__items li:last-child {
  border-bottom: 0;
}

.sale-detail__items small {
  display: block;
  color: var(--text-muted);
  font-size: 0.78rem;
}

.sale-detail__totals {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--text-muted);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sale-detail__totals > div {
  display: flex;
  justify-content: space-between;
  font-size: 0.92rem;
}

.sale-detail__debt strong {
  color: var(--danger, #c0392b);
}

.sale-detail__final {
  padding-top: 6px;
  border-top: 1px solid var(--line);
  font-size: 1.05rem;
}

.sale-detail__final strong {
  color: #205a9a;
  font-size: 1.15rem;
}

.sales-history__receipt-loading {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
}
</style>
