<script setup>
import { onMounted, onUnmounted, reactive, ref, watch } from 'vue'

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
import { useOrganizationStore } from '../../stores/organization'

const org = useOrganizationStore()

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

const STATUS_LABEL = {
  completed: 'Bajarilgan',
  canceled: 'Bekor',
  returned: 'Qaytarilgan',
  pending: 'Kutilmoqda (offline)',
}

function saleStatusIconKind(status) {
  if (status === 'completed') return 'synced'
  if (status === 'canceled') return 'canceled'
  if (status === 'returned') return 'returned'
  if (status === 'pending') return 'pending'
  return 'pending'
}

const columns = [
  {
    key: 'sold_at',
    label: 'Vaqt',
    formatter: (v) => (v ? new Date(v).toLocaleString('uz-UZ', { hour12: false }) : '—'),
    width: '160px',
  },
  { key: 'id', label: 'Chek №', width: '80px' },
  {
    key: 'branch_name',
    label: 'Filial',
    formatter: (v) => v || '—',
    width: '140px',
  },
  {
    key: 'cashier_name',
    label: 'Kassir',
    formatter: (v) => v || '—',
    width: '140px',
  },
  {
    key: 'debtor_name',
    label: 'Qarzdor',
    formatter: (v) => v || '—',
    width: '140px',
  },
  { key: 'status', label: 'Holat', width: '72px' },
  { key: 'total', label: 'Summa', width: '120px' },
]

function formatMoney(n) {
  return Number(n || 0).toLocaleString('uz-UZ', { maximumFractionDigits: 0 })
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
  <div>
    <PageHeader title="Savdolar tarixi" subtitle="Barcha cheklar, filtr va batafsil ko‘rinish" />

    <div class="card filter-bar">
      <select v-model="filters.branch" class="filter-select">
        <option value="">Barcha filiallar</option>
        <option v-for="b in org.branches" :key="b.id" :value="b.id">{{ b.name }}</option>
      </select>

      <select v-model="filters.status" class="filter-select">
        <option value="">Barcha holatlar</option>
        <option v-for="(label, code) in STATUS_LABEL" :key="code" :value="code">{{ label }}</option>
      </select>

      <input v-model="filters.date_from" type="date" class="filter-input" />
      <input v-model="filters.date_to" type="date" class="filter-input" />

      <button class="btn btn--ghost btn--sm" type="button" @click="clearFilters">
        Tozalash
      </button>
    </div>

    <DataTable
      :columns="columns"
      :rows="rows"
      :loading="loading"
      clickable
      empty-text="Hozircha savdolar yo‘q."
      @row-click="showDetail"
    >
      <template #cell:status="{ row }">
        <SyncStatusIcon
          :kind="saleStatusIconKind(row.status)"
          :label="STATUS_LABEL[row.status] || row.status"
        />
      </template>
      <template #cell:total="{ row }">
        <strong>{{ formatMoney(row.total) }}</strong>
      </template>
      <template #actions="{ row }">
        <button class="icon-btn" type="button" @click.stop="openReceipt(row)">Chop etish</button>
        <button class="icon-btn" type="button" @click.stop="showDetail(row)">Ko‘rish</button>
      </template>
    </DataTable>

    <AppModal
      :open="detailOpen"
      :title="detail ? `Chek #${detail.id}` : 'Chek'"
      width="520px"
      @close="detailOpen = false"
    >
      <div v-if="detail" class="sale-detail">
        <div class="sale-detail__meta">
          <div><span>Vaqt:</span><strong>{{ new Date(detail.sold_at).toLocaleString('uz-UZ') }}</strong></div>
          <div><span>Filial:</span><strong>{{ detail.branch_name || '—' }}</strong></div>
          <div><span>Kassir:</span><strong>{{ detail.cashier_name || '—' }}</strong></div>
          <div v-if="detail.debtor_name">
            <span>Qarzdor:</span><strong>{{ detail.debtor_name }}</strong>
          </div>
          <div><span>Holat:</span><strong>{{ STATUS_LABEL[detail.status] || detail.status }}</strong></div>
        </div>

        <h4>Mahsulotlar</h4>
        <ul class="sale-detail__items">
          <li v-for="item in detail.items" :key="item.id">
            <div>
              <strong>{{ item.product_name }}</strong>
              <small>{{ formatQuantity(item.quantity) }} × {{ formatMoney(item.unit_price) }}</small>
            </div>
            <strong>{{ formatMoney(item.line_total) }}</strong>
          </li>
        </ul>

        <h4>To‘lov</h4>
        <ul class="sale-detail__items">
          <li v-for="p in detail.payments" :key="p.id">
            <div><strong>{{ p.method === 'cash' ? 'Naqd' : p.method === 'card' ? 'Karta' : p.method }}</strong></div>
            <strong>{{ formatMoney(p.amount) }}</strong>
          </li>
        </ul>

        <div class="sale-detail__totals">
          <div><span>Subtotal:</span><strong>{{ formatMoney(detail.subtotal) }}</strong></div>
          <div v-if="Number(detail.discount) > 0">
            <span>Chegirma:</span><strong>-{{ formatMoney(detail.discount) }}</strong>
          </div>
          <div class="sale-detail__final">
            <span>Jami:</span><strong>{{ formatMoney(detail.total) }} so‘m</strong>
          </div>
          <div><span>To‘langan:</span><strong>{{ formatMoney(detail.paid) }}</strong></div>
          <div v-if="Number(detail.balance_due) > 0" class="sale-detail__debt">
            <span>Qarz:</span><strong>{{ formatMoney(detail.balance_due) }} so‘m</strong>
          </div>
          <div v-if="Number(detail.change) > 0">
            <span>Qaytim:</span><strong>{{ formatMoney(detail.change) }}</strong>
          </div>
        </div>
      </div>

      <template #footer>
        <button class="btn btn--ghost" type="button" @click="reprintFromDetail">Qayta chop etish</button>
        <button class="btn btn--primary" type="button" @click="detailOpen = false">Yopish</button>
      </template>
    </AppModal>

    <AppModal
      :open="receiptOpen"
      title="Chek chop etish"
      width="420px"
      @close="receiptOpen = false"
    >
      <div v-if="receiptLoading" class="sales-history__receipt-loading">Yuklanmoqda...</div>
      <SaleReceipt v-else-if="receiptSale" :sale="receiptSale" />

      <template #footer>
        <button class="btn btn--ghost" type="button" @click="printReceipt">Chop etish</button>
        <button class="btn btn--primary" type="button" @click="receiptOpen = false">Yopish</button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  margin-bottom: 14px;
  flex-wrap: wrap;
  align-items: center;
}

.filter-select,
.filter-input {
  border: 1px solid var(--line);
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
  padding: 9px 12px;
  font-size: 0.92rem;
  outline: none;
  min-width: 140px;
}

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

.filter-bar + :deep(.data-table) {
  margin-bottom: 0;
}
</style>
