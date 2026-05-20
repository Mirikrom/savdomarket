<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { storeToRefs } from 'pinia'

import PageHeader from '../components/PageHeader.vue'
import { numberLocaleForUi, useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { useOrganizationStore } from '../stores/organization'
import { useUiStore } from '../stores/ui'
import { products } from '../services/catalog.service'
import { sales as salesService } from '../services/sales.service'

const auth = useAuthStore()
const org = useOrganizationStore()
const { tr, branchLabel } = useI18n()
const { locale } = storeToRefs(useUiStore())

const isLoading = ref(true)
const productCount = ref(0)
const todaySummary = ref({
  all: { sales_count: 0, total_sum: 0 },
  mine: { sales_count: 0, total_sum: 0 },
})

const numberLocale = computed(() => numberLocaleForUi(locale.value))

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return tr('dash.greeting.morning')
  if (h < 18) return tr('dash.greeting.afternoon')
  return tr('dash.greeting.evening')
})

const pageTitle = computed(
  () => `${greeting.value}, ${auth.fullName || tr('dash.userFallback')}!`,
)

const pageSubtitle = computed(() => org.organization?.name || tr('dash.subtitleFallback'))

const todayTotal = computed(() => Number(todaySummary.value.all.total_sum || 0))
const todayCount = computed(() => todaySummary.value.all.sales_count || 0)

function formatMoney(value) {
  if (value === null || value === undefined) return '0'
  return Number(value).toLocaleString(numberLocale.value, { maximumFractionDigits: 0 })
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
    <PageHeader :title="pageTitle" :subtitle="pageSubtitle" />

    <section class="stat-grid">
      <div class="stat">
        <span class="stat__label">{{ tr('dash.stat.todaySales') }}</span>
        <span class="stat__value">{{ formatMoney(todayTotal) }}</span>
        <span class="stat__delta">{{ tr('dash.stat.receipts', { n: todayCount }) }}</span>
      </div>
      <div class="stat">
        <span class="stat__label">{{ tr('dash.stat.products') }}</span>
        <span class="stat__value">{{ productCount }}</span>
        <span class="stat__delta">{{ tr('dash.stat.inCatalog') }}</span>
      </div>
      <div class="stat">
        <span class="stat__label">{{ tr('dash.stat.branch') }}</span>
        <span class="stat__value" style="font-size: 1.1rem">
          {{ org.currentBranch ? branchLabel(org.currentBranch) : '—' }}
        </span>
        <span class="stat__delta">{{ tr('dash.stat.branches', { n: org.branches.length }) }}</span>
      </div>
      <div class="stat">
        <span class="stat__label">{{ tr('dash.stat.plan') }}</span>
        <span class="stat__value" style="font-size: 1.1rem">
          {{ org.plan?.name || tr('dash.stat.planNone') }}
        </span>
        <span class="stat__delta">
          <RouterLink to="/app/billing">{{ tr('dash.stat.manage') }}</RouterLink>
        </span>
      </div>
    </section>

    <div class="card">
      <h3 style="margin-top: 0">{{ tr('dash.next.title') }}</h3>
      <ol style="margin: 0; padding-left: 18px; line-height: 1.9; color: var(--text-muted)">
        <li>
          <RouterLink to="/app/categories">{{ tr('app.nav.categories') }}</RouterLink>{{ tr('dash.step.catSuffix') }}
        </li>
        <li>
          <RouterLink to="/app/products">{{ tr('app.nav.products') }}</RouterLink>{{ tr('dash.step.prodSuffix') }}
        </li>
        <li>
          <RouterLink to="/app/inventory">{{ tr('dash.step.warehouseLink') }}</RouterLink>{{ tr('dash.step.invSuffix') }}
        </li>
        <li>
          <RouterLink to="/app/pos">{{ tr('dash.step.posLink') }}</RouterLink>{{ tr('dash.step.posSuffix') }}
        </li>
        <li>
          <RouterLink to="/app/users">{{ tr('app.nav.users') }}</RouterLink>{{ tr('dash.step.usersSuffix') }}
        </li>
      </ol>
    </div>
  </div>
</template>
