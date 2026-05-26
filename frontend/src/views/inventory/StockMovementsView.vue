<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import { useI18n } from '../../i18n'
import { products as productsApi } from '../../services/catalog.service'
import { stockMovements } from '../../services/inventory.service'
import { useOrganizationStore } from '../../stores/organization'

const router = useRouter()
const org = useOrganizationStore()
const { tr } = useI18n()

const rows = ref([])
const productList = ref([])
const loading = ref(true)

const filters = reactive({
  branch: '',
  product: '',
  movement_type: '',
  date_from: '',
  date_to: '',
})

const TYPE_LABELS = {
  in: 'Kirim',
  out: 'Chiqim',
  adjust: 'Tuzatish',
  return: 'Qaytarish',
  product_create: "Mahsulot qo'shildi",
}

const TYPE_CLASS = {
  in: 'pill pill--green',
  out: 'pill pill--red',
  adjust: 'pill pill--blue',
  return: 'pill pill--yellow',
  product_create: 'pill pill--purple',
}

const columns = [
  {
    key: 'created_at',
    label: 'Sana',
    formatter: (v) => (v ? new Date(v).toLocaleString('uz-UZ', { hour12: false }) : '—'),
    width: '160px',
  },
  { key: 'product_name', label: 'Mahsulot' },
  {
    key: 'branch_name',
    label: 'Filial',
    formatter: (v) => v || '—',
    width: '140px',
  },
  { key: 'movement_type', label: 'Turi', width: '110px' },
  { key: 'quantity', label: 'Miqdor', width: '110px' },
  {
    key: 'unit_cost',
    label: 'Tannarx',
    formatter: (v) => (Number(v) ? Number(v).toLocaleString('uz-UZ') : '—'),
    width: '120px',
  },
  {
    key: 'created_by_name',
    label: 'Kim',
    formatter: (v) => v || '—',
    width: '140px',
  },
  { key: 'note', label: 'Izoh' },
]

async function fetchProducts() {
  productList.value = await productsApi.list()
}

async function fetchRows() {
  loading.value = true
  try {
    const params = {}
    if (filters.branch) params.branch = filters.branch
    if (filters.product) params.product = filters.product
    if (filters.movement_type) params.movement_type = filters.movement_type
    if (filters.date_from) params.date_from = filters.date_from
    if (filters.date_to) params.date_to = filters.date_to
    rows.value = await stockMovements.list(params)
  } finally {
    loading.value = false
  }
}

function clearFilters() {
  filters.branch = ''
  filters.product = ''
  filters.movement_type = ''
  filters.date_from = ''
  filters.date_to = ''
}

watch(filters, fetchRows, { deep: true })

onMounted(async () => {
  await fetchProducts()
  if (org.currentBranchId) filters.branch = String(org.currentBranchId)
  await fetchRows()
})
</script>

<template>
  <div>
    <PageHeader
      :title="tr('page.movements.title')"
      :subtitle="tr('page.movements.subtitle')"
    >
      <template #actions>
        <button class="btn btn--ghost" @click="router.push('/app/inventory')">
          {{ tr('page.movements.backStock') }}
        </button>
        <button class="btn btn--primary" @click="router.push('/app/inventory/receipt')">
          {{ tr('page.movements.receiptBtn') }}
        </button>
        <button class="btn btn--ghost" @click="router.push('/app/inventory/adjust')">
          {{ tr('page.movements.issueBtn') }}
        </button>
      </template>
    </PageHeader>

    <div class="card filter-bar">
      <select v-model="filters.branch" class="filter-select">
        <option value="">{{ tr('page.movements.filterAllBranches') }}</option>
        <option v-for="b in org.branches" :key="b.id" :value="b.id">{{ b.name }}</option>
      </select>

      <select v-model="filters.product" class="filter-select">
        <option value="">Barcha mahsulotlar</option>
        <option v-for="p in productList" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>

      <select v-model="filters.movement_type" class="filter-select">
        <option value="">Barcha turlar</option>
        <option v-for="(label, code) in TYPE_LABELS" :key="code" :value="code">{{ label }}</option>
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
      empty-text="Tanlangan filtrlar bo‘yicha harakat topilmadi."
    >
      <template #cell:movement_type="{ row }">
        <span :class="TYPE_CLASS[row.movement_type] || 'pill'">
          {{ TYPE_LABELS[row.movement_type] || row.movement_type }}
        </span>
      </template>
    </DataTable>
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

.pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 500;
  background: #eef1f6;
  color: var(--text);
}

.pill--green {
  background: #e3f5e8;
  color: #2c7a3d;
}

.pill--red {
  background: #fdece4;
  color: #b1442b;
}

.pill--blue {
  background: #e5efff;
  color: #205a9a;
}

.pill--yellow {
  background: #fff4d6;
  color: #8a6708;
}

.pill--purple {
  background: #efe8f5;
  color: #5c3d7a;
}
</style>
