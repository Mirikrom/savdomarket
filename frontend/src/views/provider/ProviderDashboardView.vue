<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import providerService from '../../services/provider.service'

const route = useRoute()
const stats = ref(null)
const loading = ref(true)
const error = ref(null)

function fmt(n) {
  if (n == null) return '0'
  const num = typeof n === 'string' ? parseFloat(n) : n
  if (Number.isNaN(num)) return String(n)
  return num.toLocaleString('uz-UZ', { maximumFractionDigits: 0 })
}

async function load() {
  loading.value = true
  error.value = null
  try {
    stats.value = await providerService.stats()
  } catch (err) {
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

/* Tashkilot qo'shish/o'chirishdan keyin bu yerga qaytganda ro'yxat bilan bir xil raqamlar */
watch(
  () => route.name,
  (name) => {
    if (name === 'provider-dashboard') load()
  },
  { immediate: true },
)
</script>

<template>
  <div class="prov-page">
    <header class="prov-page__header">
      <div>
        <h1 class="prov-page__title">Boshqaruv paneli</h1>
        <p class="prov-page__subtitle">Tashkilotlar, obunalar va foydalanuvchilar</p>
      </div>
      <button class="prov-btn" @click="load" :disabled="loading">
        {{ loading ? 'Yuklanmoqda...' : 'Yangilash' }}
      </button>
    </header>

    <p v-if="error" class="prov-error">{{ error }}</p>

    <section v-if="stats" class="prov-grid">
      <article class="prov-card">
        <div class="prov-card__label">Tashkilotlar</div>
        <div class="prov-card__value">{{ fmt(stats.organizations.total) }}</div>
        <div class="prov-card__meta">
          <span class="prov-badge prov-badge--ok">{{ stats.organizations.active }} faol</span>
          <span class="prov-badge prov-badge--warn" v-if="stats.organizations.suspended">
            {{ stats.organizations.suspended }} bloklangan
          </span>
        </div>
        <div class="prov-card__hint">+{{ stats.organizations.new_30d }} oxirgi 30 kun</div>
      </article>

      <article class="prov-card">
        <div class="prov-card__label">Faol obunalar</div>
        <div class="prov-card__value">{{ fmt(stats.subscriptions.active_total) }}</div>
        <div class="prov-card__meta">
          <span class="prov-badge prov-badge--warn" v-if="stats.subscriptions.expiring_soon">
            {{ stats.subscriptions.expiring_soon }} tugayapti
          </span>
          <span class="prov-badge prov-badge--danger" v-if="stats.subscriptions.expired">
            {{ stats.subscriptions.expired }} tugagan
          </span>
        </div>
        <div class="prov-card__hint">7 kun ichida tugaydiganlar</div>
      </article>

      <article class="prov-card">
        <div class="prov-card__label">Foydalanuvchilar</div>
        <div class="prov-card__value">{{ fmt(stats.users.total) }}</div>
        <div class="prov-card__meta">
          <span class="prov-badge prov-badge--ok">{{ stats.users.active_30d }} faol (30 kun)</span>
        </div>
      </article>
    </section>

    <section v-if="stats" class="prov-section">
      <h2 class="prov-section__title">Tariflar bo'yicha taqsimot</h2>
      <div class="prov-plans">
        <article
          v-for="row in stats.subscriptions.by_plan"
          :key="row.plan__code"
          class="prov-plan"
        >
          <div class="prov-plan__name">{{ row.plan__name || row.plan__code }}</div>
          <div class="prov-plan__count">{{ row.count }}</div>
          <div class="prov-plan__label">aktiv tashkilot</div>
        </article>
        <article v-if="!stats.subscriptions.by_plan.length" class="prov-plan prov-plan--empty">
          Hozircha tariflar bo'yicha ma'lumot yo'q
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.prov-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 22px;
  gap: 12px;
  flex-wrap: wrap;
}
.prov-page__title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #fff;
}
.prov-page__subtitle {
  margin: 4px 0 0;
  color: #94a3b8;
  font-size: 13px;
}
.prov-btn {
  background: linear-gradient(135deg, #f97316, #ef4444);
  color: #fff;
  border: 0;
  padding: 9px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.prov-btn:disabled {
  opacity: 0.6;
  cursor: progress;
}

.prov-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 26px;
}
.prov-card {
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 14px;
  padding: 18px;
}
.prov-card__label {
  color: #94a3b8;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}
.prov-card__value {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin-top: 8px;
}
.prov-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}
.prov-card__hint {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}

.prov-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #cbd5e1;
  font-size: 11px;
  font-weight: 600;
}
.prov-badge--ok {
  background: rgba(34, 197, 94, 0.15);
  color: #4ade80;
}
.prov-badge--warn {
  background: rgba(234, 179, 8, 0.15);
  color: #facc15;
}
.prov-badge--danger {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.prov-section__title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
}
.prov-plans {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.prov-plan {
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}
.prov-plan__name {
  color: #94a3b8;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 600;
}
.prov-plan__count {
  font-size: 28px;
  font-weight: 700;
  color: #fb923c;
  margin: 6px 0 2px;
}
.prov-plan__label {
  font-size: 12px;
  color: #64748b;
}
.prov-plan--empty {
  grid-column: 1 / -1;
  color: #64748b;
  font-size: 13px;
  text-align: center;
}

.prov-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 16px;
}
</style>
