<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import { numberLocaleForUi, useI18n } from '../../i18n'
import { stockLevels } from '../../services/inventory.service'
import { useOrganizationStore } from '../../stores/organization'

const router = useRouter()
const org = useOrganizationStore()
const { tr, locale } = useI18n()

function numberLocale() {
  return numberLocaleForUi(locale.value)
}

const rows = ref([])
const summary = ref({ products_count: 0, low_stock_count: 0, total_quantity: 0 })
const loading = ref(true)
const search = ref('')
const onlyLow = ref(false)
const branchFilter = ref('')

const UNIT_LABEL = computed(() => ({
  piece: tr('page.inventory.unitPiece'),
  kg: 'kg',
  liter: 'l',
  pack: tr('page.inventory.unitPack'),
}))

const columns = computed(() => [
  {
    key: 'product_name',
    label: tr('page.inventory.colProduct'),
  },
  {
    key: 'product_sku',
    label: 'SKU',
    width: '120px',
  },
  {
    key: 'category_name',
    label: tr('page.inventory.colCategory'),
    formatter: (v) => v || '—',
    width: '140px',
  },
  {
    key: 'branch_name',
    label: tr('page.inventory.colBranch'),
    formatter: (v) => v || '—',
    width: '140px',
  },
  {
    key: 'quantity',
    label: tr('page.inventory.colQty'),
    width: '140px',
  },
  {
    key: 'min_stock',
    label: tr('page.inventory.colMin'),
    width: '120px',
  },
])

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return rows.value
  return rows.value.filter(
    (r) =>
      r.product_name?.toLowerCase().includes(q) ||
      r.product_sku?.toLowerCase().includes(q),
  )
})

function formatQty(row) {
  const n = Number(row.quantity ?? 0)
  const unit = UNIT_LABEL.value[row.product_unit] || ''
  return `${n.toLocaleString(numberLocale(), { maximumFractionDigits: 3 })} ${unit}`.trim()
}

async function fetchLevels() {
  loading.value = true
  try {
    const params = {}
    if (branchFilter.value) params.branch = branchFilter.value
    if (onlyLow.value) params.only_low = 1
    const data = await stockLevels.list(params)
    rows.value = data.results || []
    summary.value = data.summary || {
      products_count: rows.value.length,
      low_stock_count: 0,
      total_quantity: 0,
    }
  } finally {
    loading.value = false
  }
}

watch(() => org.currentBranchId, (newId) => {
  if (!branchFilter.value && newId) {
    branchFilter.value = String(newId)
    fetchLevels()
  }
})

watch([branchFilter, onlyLow], fetchLevels)

onMounted(() => {
  if (org.currentBranchId) branchFilter.value = String(org.currentBranchId)
  fetchLevels()
})
</script>

<template>
  <div>
    <PageHeader
      :title="tr('page.inventory.title')"
      :subtitle="tr('page.inventory.subtitle')"
    >
      <template #actions>
        <button class="btn btn--ghost" @click="router.push('/app/inventory/movements')">
          {{ tr('page.inventory.historyBtn') }}
        </button>
        <button class="btn btn--primary" @click="router.push('/app/inventory/receipt')">
          {{ tr('page.inventory.receiptBtn') }}
        </button>
      </template>
    </PageHeader>

    <div class="stat-grid">
      <div class="stat-card">
        <span class="stat-card__label">{{ tr('page.inventory.statProducts') }}</span>
        <strong class="stat-card__value">{{ summary.products_count }}</strong>
      </div>
      <div class="stat-card stat-card--warn">
        <span class="stat-card__label">{{ tr('page.inventory.statLow') }}</span>
        <strong class="stat-card__value">{{ summary.low_stock_count }}</strong>
      </div>
      <div class="stat-card">
        <span class="stat-card__label">{{ tr('page.inventory.statTotalQty') }}</span>
        <strong class="stat-card__value">
          {{ Number(summary.total_quantity).toLocaleString(numberLocale(), { maximumFractionDigits: 2 }) }}
        </strong>
      </div>
    </div>

    <div class="card filter-bar">
      <input
        v-model="search"
        class="search-input"
        type="search"
        :placeholder="tr('page.inventory.searchPlaceholder')"
      />
      <select v-model="branchFilter" class="filter-select">
        <option value="">{{ tr('page.movements.filterAllBranches') }}</option>
        <option v-for="b in org.branches" :key="b.id" :value="b.id">{{ b.name }}</option>
      </select>
      <label class="filter-check">
        <input v-model="onlyLow" type="checkbox" />
        <span>{{ tr('page.inventory.onlyLow') }}</span>
      </label>
    </div>

    <DataTable
      :columns="columns"
      :rows="filteredRows"
      :loading="loading"
      :empty-text="tr('page.inventory.emptyTable')"
    >
      <template #cell:quantity="{ row }">
        <span :class="row.is_low ? 'qty-pill qty-pill--low' : 'qty-pill'">
          {{ formatQty(row) }}
        </span>
      </template>
      <template #cell:min_stock="{ row }">
        {{ Number(row.min_stock).toLocaleString(numberLocale(), { maximumFractionDigits: 3 }) }}
      </template>
    </DataTable>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 14px;
}

.stat-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.stat-card__label {
  font-size: 0.8rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.stat-card__value {
  font-size: 1.4rem;
  font-weight: 600;
  color: var(--text);
}

.stat-card--warn {
  border-color: #f4c89d;
  background: linear-gradient(135deg, #fff4e7 0%, #fff 100%);
}

.stat-card--warn .stat-card__value {
  color: #c46b14;
}

.filter-bar {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  margin-bottom: 14px;
  flex-wrap: wrap;
  align-items: center;
}

.search-input,
.filter-select {
  border: 1px solid var(--line);
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  font-size: 0.92rem;
  outline: none;
}

.search-input {
  flex: 1 1 260px;
}

.filter-select {
  min-width: 180px;
}

.filter-check {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text);
  font-size: 0.92rem;
  cursor: pointer;
}

.qty-pill {
  display: inline-block;
  background: #eaf3ff;
  color: #205a9a;
  padding: 4px 10px;
  border-radius: 999px;
  font-weight: 500;
  font-size: 0.88rem;
}

.qty-pill--low {
  background: #fde8e0;
  color: #b1442b;
}

@media (max-width: 640px) {
  .stat-grid {
    grid-template-columns: 1fr 1fr;
  }
  .stat-grid .stat-card:first-child {
    grid-column: span 2;
  }
}
</style>
