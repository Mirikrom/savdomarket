<script setup>
import { computed, onMounted, ref } from 'vue'

import PageHeader from '../components/PageHeader.vue'
import { useAuthStore } from '../stores/auth'
import { useOrganizationStore } from '../stores/organization'
import { products } from '../services/catalog.service'
import { sales as salesService } from '../services/sales.service'

const auth = useAuthStore()
const org = useOrganizationStore()

const isLoading = ref(true)
const productCount = ref(0)
const todaySummary = ref({
  all: { sales_count: 0, total_sum: 0 },
  mine: { sales_count: 0, total_sum: 0 },
})

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return 'Xayrli tong'
  if (h < 18) return 'Xayrli kun'
  return 'Xayrli kech'
})

const todayTotal = computed(() => Number(todaySummary.value.all.total_sum || 0))
const todayCount = computed(() => todaySummary.value.all.sales_count || 0)

function formatMoney(value) {
  if (value === null || value === undefined) return '0'
  return Number(value).toLocaleString('uz-UZ', { maximumFractionDigits: 0 })
}

onMounted(async () => {
  try {
    const params = org.currentBranchId ? { branch: org.currentBranchId } : {}
    const [allProducts, summary] = await Promise.allSettled([
      products.list(),
      salesService.todaySummary(params),
    ])
    if (allProducts.status === 'fulfilled') productCount.value = allProducts.value.length
    if (summary.status === 'fulfilled') todaySummary.value = summary.value
  } finally {
    isLoading.value = false
  }
})
</script>

<template>
  <div>
    <PageHeader
      :title="`${greeting}, ${auth.fullName || 'foydalanuvchi'}!`"
      :subtitle="org.organization?.name || 'Boshqaruv paneliga xush kelibsiz.'"
    />

    <section class="stat-grid">
      <div class="stat">
        <span class="stat__label">Bugungi savdolar (so‘m)</span>
        <span class="stat__value">{{ formatMoney(todayTotal) }}</span>
        <span class="stat__delta">{{ todayCount }} ta chek</span>
      </div>
      <div class="stat">
        <span class="stat__label">Mahsulotlar soni</span>
        <span class="stat__value">{{ productCount }}</span>
        <span class="stat__delta">Katalogda</span>
      </div>
      <div class="stat">
        <span class="stat__label">Joriy filial</span>
        <span class="stat__value" style="font-size: 1.1rem">
          {{ org.currentBranch?.name || '—' }}
        </span>
        <span class="stat__delta">{{ org.branches.length }} ta filial</span>
      </div>
      <div class="stat">
        <span class="stat__label">Tarif</span>
        <span class="stat__value" style="font-size: 1.1rem">
          {{ org.plan?.name || 'Tariflashtirilmagan' }}
        </span>
        <span class="stat__delta">
          <RouterLink to="/app/billing">Boshqarish</RouterLink>
        </span>
      </div>
    </section>

    <div class="card">
      <h3 style="margin-top: 0">Boshlash uchun keyingi qadamlar</h3>
      <ol style="margin: 0; padding-left: 18px; line-height: 1.9; color: var(--text-muted)">
        <li>
          <RouterLink to="/app/categories">Kategoriyalar</RouterLink> qo‘shing
        </li>
        <li>
          <RouterLink to="/app/products">Mahsulotlar</RouterLink> katalogini to‘ldiring
        </li>
        <li>
          <RouterLink to="/app/inventory">Omborga</RouterLink> kirim qiling
        </li>
        <li>
          <RouterLink to="/app/pos">Kassada</RouterLink> savdo qiling
        </li>
        <li>
          <RouterLink to="/app/users">Xodimlar</RouterLink> ni rollarga biriktiring
        </li>
      </ol>
    </div>
  </div>
</template>
