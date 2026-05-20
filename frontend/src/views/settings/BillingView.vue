<script setup>
import { computed, onMounted, ref } from 'vue'

import PageHeader from '../../components/PageHeader.vue'
import { plans, subscriptions } from '../../services/subscription.service'
import { useOrganizationStore } from '../../stores/organization'
import { numberLocaleForUi, useI18n } from '../../i18n'

const org = useOrganizationStore()
const { tr, locale } = useI18n()

const planList = ref([])
const loading = ref(true)

const currentPlanCode = computed(() => org.plan?.code || null)

function numberLocale() {
  return numberLocaleForUi(locale.value)
}

function formatPrice(value) {
  if (value === null || value === undefined) return '0'
  return Number(value).toLocaleString(numberLocale(), { maximumFractionDigits: 0 })
}

function endsAtLabel(value) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString(numberLocale())
}

async function load() {
  loading.value = true
  try {
    const [pl] = await Promise.all([plans.list(), subscriptions.current()])
    planList.value = pl
    await org.fetchCurrentPlan()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHeader :title="tr('page.billing.title')" :subtitle="tr('page.billing.subtitle')" />

    <div v-if="loading" class="app-loading">{{ tr('page.billing.loading') }}</div>

    <template v-else>
      <div class="card" style="margin-bottom: 18px">
        <div style="display: flex; justify-content: space-between; gap: 18px; flex-wrap: wrap">
          <div>
            <h3 style="margin: 0 0 4px">{{ org.plan?.name || tr('page.billing.noPlan') }}</h3>
            <p style="margin: 0; color: var(--text-muted)">
              <template v-if="org.subscription">
                {{ tr('page.billing.endsAt') }}
                <strong>{{ endsAtLabel(org.subscription.ends_at) }}</strong> ·
                {{ tr('page.billing.status') }} <strong>{{ org.subscription.status }}</strong>
              </template>
              <template v-else>{{ tr('page.billing.noActiveSub') }}</template>
            </p>
          </div>
          <div v-if="org.plan" style="text-align: right">
            <div style="font-size: 1.4rem; font-weight: 700">
              {{ formatPrice(org.plan.price_monthly) }} {{ tr('page.billing.currencySom') }}
            </div>
            <small style="color: var(--text-muted)">{{ tr('page.billing.perMonth') }}</small>
          </div>
        </div>
      </div>

      <div class="plan-grid">
        <div
          v-for="p in planList"
          :key="p.id"
          class="plan-card"
          :class="{ 'is-active': p.code === currentPlanCode }"
        >
          <header>
            <h3>{{ p.name }}</h3>
            <span :class="['plan-tag__chip', `plan-tag__chip--${p.code}`]">
              {{ p.code === 'pro' ? 'Pro' : 'Lite' }}
            </span>
          </header>

          <p class="plan-card__price">
            <strong>{{ formatPrice(p.price_monthly) }}</strong>
            <small>{{ tr('page.billing.somPerMonth') }}</small>
          </p>

          <ul class="plan-card__list">
            <li>{{ tr('page.billing.limitUsers', { n: p.max_users }) }}</li>
            <li>{{ tr('page.billing.limitProducts', { n: p.max_products }) }}</li>
            <li>{{ tr('page.billing.limitBranches', { n: p.max_branches }) }}</li>
            <li v-if="p.feature_flags?.batch_tracking">{{ tr('page.billing.featureBatch') }}</li>
            <li v-if="p.feature_flags?.products">{{ tr('page.billing.featureProducts') }}</li>
          </ul>

          <button
            v-if="p.code !== currentPlanCode"
            class="btn btn--primary"
            disabled
            :title="tr('page.billing.paySoonHint')"
          >
            {{ tr('page.billing.btnChoose') }}
          </button>
          <button v-else class="btn btn--ghost" disabled>{{ tr('page.billing.btnCurrent') }}</button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.plan-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 14px;
}

.plan-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.plan-card.is-active {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(31, 79, 163, 0.15);
}

.plan-card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 0;
}

.plan-card h3 {
  margin: 0;
  font-size: 1.1rem;
}

.plan-card__price {
  margin: 0;
  font-size: 1.3rem;
}

.plan-card__price strong {
  font-weight: 700;
}

.plan-card__price small {
  color: var(--text-muted);
  font-size: 0.84rem;
  margin-left: 4px;
}

.plan-card__list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  color: var(--text-muted);
  font-size: 0.88rem;
}

.plan-card__list strong {
  color: var(--text);
}
</style>
