<script setup>
import { onMounted, ref } from 'vue'

import providerService from '../../services/provider.service'

const plans = ref([])
const loading = ref(true)
const error = ref(null)
const savingId = ref(null)

const editOpen = ref(false)
const editForm = ref(null)
const editFlagsJson = ref('{}')
const editError = ref('')

function fmtMoney(n) {
  if (n == null) return '0'
  const num = typeof n === 'string' ? parseFloat(n) : n
  return num.toLocaleString('uz-UZ', { maximumFractionDigits: 0 })
}

async function load() {
  loading.value = true
  error.value = null
  try {
    plans.value = await providerService.plans.list()
  } catch (err) {
    error.value = err.response?.data?.detail || err.message
    plans.value = []
  } finally {
    loading.value = false
  }
}

function openEdit(p) {
  editForm.value = { ...p }
  try {
    editFlagsJson.value = JSON.stringify(p.feature_flags || {}, null, 2)
  } catch {
    editFlagsJson.value = '{}'
  }
  editError.value = ''
  editOpen.value = true
}

function closeEdit() {
  editOpen.value = false
  editForm.value = null
}

async function saveEdit() {
  if (!editForm.value) return
  let flags = {}
  try {
    flags = JSON.parse(editFlagsJson.value || '{}')
    if (typeof flags !== 'object' || Array.isArray(flags)) throw new Error('object')
  } catch {
    editError.value = 'Feature flags noto‘g‘ri JSON. {} formatida bo‘lsin.'
    return
  }
  editError.value = ''
  savingId.value = editForm.value.id
  try {
    await providerService.plans.patch(editForm.value.id, {
      name: editForm.value.name,
      price_monthly: editForm.value.price_monthly,
      max_users: editForm.value.max_users,
      max_products: editForm.value.max_products,
      max_branches: editForm.value.max_branches,
      feature_flags: flags,
      is_active: editForm.value.is_active,
    })
    closeEdit()
    await load()
  } catch (err) {
    editError.value =
      err.response?.data?.detail ||
      Object.values(err.response?.data || {})
        .flat()
        .join(' ') ||
      err.message
  } finally {
    savingId.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="prov-page">
    <header class="prov-page__header">
      <div>
        <h1 class="prov-page__title">Tariflar</h1>
        <p class="prov-page__subtitle">Lite / Pro — narx va limitlar (kod o‘zgarmaydi)</p>
      </div>
      <button class="prov-btn" type="button" :disabled="loading" @click="load">
        {{ loading ? 'Yuklanmoqda...' : 'Yangilash' }}
      </button>
    </header>

    <p v-if="error" class="prov-error">{{ error }}</p>

    <div class="prov-table-wrap">
      <table class="prov-table">
        <thead>
          <tr>
            <th>Kod</th>
            <th>Nom</th>
            <th>Oylik narx</th>
            <th>Limitlar</th>
            <th>Faol obuna</th>
            <th>Holat</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7" class="prov-table__empty">Yuklanmoqda...</td>
          </tr>
          <tr v-for="p in plans" :key="p.id">
            <td>
              <span class="prov-pill" :class="`is-${p.code}`">{{ p.code }}</span>
            </td>
            <td>{{ p.name }}</td>
            <td>{{ fmtMoney(p.price_monthly) }} so'm</td>
            <td class="prov-muted">
              xodim {{ p.max_users }} · mahsulot {{ p.max_products }} · filial {{ p.max_branches }}
            </td>
            <td>{{ p.active_subscriptions ?? 0 }}</td>
            <td>
              <span class="prov-badge" :class="p.is_active ? 'prov-badge--ok' : 'prov-badge--danger'">
                {{ p.is_active ? 'Sotuvda' : "O'chirilgan" }}
              </span>
            </td>
            <td>
              <button type="button" class="prov-btn prov-btn--sm prov-btn--ghost" @click="openEdit(p)">
                Tahrirlash
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="editOpen && editForm" class="prov-modal" @click.self="closeEdit">
      <div class="prov-modal__card prov-modal__card--wide">
        <h3>Tarif: {{ editForm.code }}</h3>
        <p v-if="editError" class="prov-error prov-error--compact">{{ editError }}</p>
        <div class="prov-form-grid">
          <label class="prov-field">
            <span>Nom</span>
            <input v-model="editForm.name" type="text" class="prov-input" />
          </label>
          <label class="prov-field">
            <span>Oylik narx (so'm)</span>
            <input v-model.number="editForm.price_monthly" type="number" min="0" step="1000" class="prov-input" />
          </label>
          <label class="prov-field">
            <span>Max. xodim</span>
            <input v-model.number="editForm.max_users" type="number" min="1" class="prov-input" />
          </label>
          <label class="prov-field">
            <span>Max. mahsulot</span>
            <input v-model.number="editForm.max_products" type="number" min="1" class="prov-input" />
          </label>
          <label class="prov-field">
            <span>Max. filial</span>
            <input v-model.number="editForm.max_branches" type="number" min="1" class="prov-input" />
          </label>
          <label class="prov-field prov-field--full">
            <span>Feature flags (JSON)</span>
            <textarea v-model="editFlagsJson" class="prov-input prov-textarea" rows="6" spellcheck="false" />
          </label>
          <label class="prov-field prov-field--row">
            <input v-model="editForm.is_active" type="checkbox" />
            <span>Tarif sotuvda (yangi obunalar uchun)</span>
          </label>
        </div>
        <div class="prov-modal__actions">
          <button type="button" class="prov-btn prov-btn--ghost" @click="closeEdit">Bekor</button>
          <button type="button" class="prov-btn" :disabled="savingId" @click="saveEdit">
            {{ savingId ? 'Saqlanmoqda...' : 'Saqlash' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.prov-page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
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
.prov-btn--ghost {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #cbd5e1;
}
.prov-btn--ghost:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}
.prov-btn--sm {
  padding: 7px 12px;
  font-size: 12px;
}

.prov-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 12px;
}
.prov-error--compact {
  margin-bottom: 10px;
}

.prov-table-wrap {
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  overflow: auto;
}
.prov-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.prov-table th {
  text-align: left;
  padding: 12px 14px;
  color: #94a3b8;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-weight: 600;
}
.prov-table td {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  color: #e5e7eb;
  vertical-align: middle;
}
.prov-table__empty {
  padding: 28px;
  text-align: center;
  color: #64748b;
}
.prov-muted {
  color: #94a3b8;
  font-size: 12px;
}
.prov-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.06);
  color: #cbd5e1;
}
.prov-pill.is-lite {
  background: rgba(59, 130, 246, 0.15);
  color: #60a5fa;
}
.prov-pill.is-pro {
  background: rgba(249, 115, 22, 0.15);
  color: #fb923c;
}
.prov-badge {
  display: inline-flex;
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
.prov-badge--danger {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.prov-modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: grid;
  place-items: center;
  padding: 20px;
  z-index: 50;
}
.prov-modal__card {
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 24px;
  width: min(100%, 520px);
}
.prov-modal__card--wide {
  width: min(100%, 640px);
}
.prov-modal__card h3 {
  margin: 0 0 14px;
  color: #fff;
  font-size: 16px;
}
.prov-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.prov-field {
  display: block;
}
.prov-field--full {
  grid-column: 1 / -1;
}
.prov-field--row {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #cbd5e1;
  font-size: 13px;
}
.prov-field span {
  display: block;
  margin-bottom: 6px;
  color: #94a3b8;
  font-size: 12px;
}
.prov-input {
  width: 100%;
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #e5e7eb;
  padding: 9px 12px;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}
.prov-textarea {
  font-family: ui-monospace, monospace;
  font-size: 12px;
  resize: vertical;
}
.prov-modal__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
@media (max-width: 600px) {
  .prov-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
