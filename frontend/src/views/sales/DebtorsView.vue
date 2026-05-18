<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import AppModal from '../../components/AppModal.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import { POS_SHELL_QUERY_KEY, POS_SHELL_QUERY_VALUE } from '../../posShellQuery'
import { isOfflineMode } from '../../offline/connectivity'
import { createOfflineDebtor, loadDebtorsMerged } from '../../offline/offlineDebtors'
import { debtors as debtorsApi } from '../../services/debtors.service'
import { hydrateOrganizationStore, resolvePosIds } from '../../offline/posContext'
import { useOrganizationStore } from '../../stores/organization'

const route = useRoute()
const org = useOrganizationStore()

const isPosMode = computed(() => {
  const q = route.query[POS_SHELL_QUERY_KEY]
  return q === POS_SHELL_QUERY_VALUE || q === 'true'
})

const rows = ref([])
const loading = ref(true)
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
})

const editForm = reactive({
  name: '',
  phone: '',
  note: '',
})

const payForm = reactive({
  amount: '',
  method: 'cash',
  note: '',
})

const columns = [
  { key: 'name', label: 'Ism', width: '200px' },
  { key: 'phone', label: 'Telefon', width: '140px', formatter: (v) => v || '—' },
  { key: 'balance_due', label: 'Qarz', width: '120px' },
  { key: 'note', label: 'Izoh', formatter: (v) => v || '—' },
]

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

function formatMoney(n) {
  return Number(n || 0).toLocaleString('uz-UZ', { maximumFractionDigits: 0 })
}

async function fetchDebtors() {
  loading.value = true
  try {
    await hydrateOrganizationStore(org)
    const { orgId } = await resolvePosIds(org)
    if (isOfflineMode()) {
      rows.value = orgId ? await loadDebtorsMerged(orgId) : []
      return
    }
    const params = {}
    if (!isPosMode.value && search.value.trim()) params.q = search.value.trim()
    rows.value = await debtorsApi.list(params)
    if (orgId) {
      const { syncDebtorsToIndexedDB } = await import('../../offline/fullSync')
      await syncDebtorsToIndexedDB(orgId).catch(() => {})
    }
  } catch {
    const { orgId } = await resolvePosIds(org)
    rows.value = orgId ? await loadDebtorsMerged(orgId) : []
  } finally {
    loading.value = false
  }
}

function resetCreateForm() {
  createForm.name = ''
  createForm.phone = ''
  createForm.note = ''
}

function openCreate() {
  apiError.value = ''
  resetCreateForm()
  createOpen.value = true
}

async function submitCreate() {
  apiError.value = ''
  if (!createForm.name.trim()) {
    apiError.value = 'Ism kiritilishi shart.'
    return
  }
  saving.value = true
  try {
    const { orgId } = await resolvePosIds(org)
    if (isOfflineMode()) {
      await createOfflineDebtor(orgId, {
        name: createForm.name.trim(),
        phone: createForm.phone.trim(),
        note: createForm.note.trim(),
      })
    } else {
      await debtorsApi.create({
        name: createForm.name.trim(),
        phone: createForm.phone.trim(),
        note: createForm.note.trim(),
      })
    }
    createOpen.value = false
    await fetchDebtors()
  } catch (error) {
    apiError.value = error?.response?.data?.name?.[0] || error?.response?.data?.detail || 'Saqlab bo‘lmadi.'
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
  editOpen.value = true
}

async function submitEdit() {
  apiError.value = ''
  if (!editForm.name.trim()) {
    apiError.value = 'Ism kiritilishi shart.'
    return
  }
  saving.value = true
  try {
    const updated = await debtorsApi.update(editingId.value, {
      name: editForm.name.trim(),
      phone: editForm.phone.trim(),
      note: editForm.note.trim(),
    })
    const idx = rows.value.findIndex((r) => r.id === editingId.value)
    if (idx >= 0) rows.value[idx] = updated
    editOpen.value = false
  } catch (error) {
    apiError.value = error?.response?.data?.name?.[0] || error?.response?.data?.detail || 'Yangilab bo‘lmadi.'
  } finally {
    saving.value = false
  }
}

async function removeDebtor(row) {
  if (!confirm(`"${row.name}" qarzdor ro‘yxatdan o‘chirilsinmi?`)) return
  try {
    await debtorsApi.remove(row.id)
    rows.value = rows.value.filter((r) => r.id !== row.id)
  } catch (error) {
    alert(error?.response?.data?.detail || 'O‘chirib bo‘lmadi.')
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
    apiError.value = 'Filial tanlanmagan.'
    return
  }
  const amount = Number(payForm.amount || 0)
  if (amount <= 0) {
    apiError.value = 'Summa 0 dan katta bo‘lishi kerak.'
    return
  }
  if (amount > Number(selected.value.balance_due)) {
    apiError.value = 'Summa qarzdan oshmasligi kerak.'
    return
  }
  saving.value = true
  try {
    const result = await debtorsApi.pay(selected.value.id, {
      branch: org.currentBranchId,
      amount: payForm.amount,
      method: payForm.method,
      note: payForm.note,
    })
    const idx = rows.value.findIndex((r) => r.id === selected.value.id)
    if (idx >= 0 && result.debtor) rows.value[idx] = result.debtor
    payOpen.value = false
  } catch (error) {
    const data = error?.response?.data
    apiError.value = data?.amount?.[0] || data?.detail || 'To‘lov saqlanmadi.'
  } finally {
    saving.value = false
  }
}

onMounted(fetchDebtors)
</script>

<template>
  <div :class="['debtors-page', isPosMode ? 'debtors-page--pos' : '']">
    <PageHeader
      v-if="!isPosMode"
      title="Qarzdorlar"
      subtitle="Qarzdorlarni boshqarish, tahrirlash va qarzni qoplash"
    >
      <template #actions>
        <button class="btn btn--primary" type="button" @click="openCreate">+ Yangi qarzdor</button>
      </template>
    </PageHeader>

    <header v-else class="debtors-pos-head">
      <div>
        <h1 class="debtors-pos-head__title">Qarzdorlar</h1>
        <p class="debtors-pos-head__sub">Qarzni ko‘rish va pul kiritish</p>
      </div>
      <button class="debtors-pos-head__add" type="button" @click="openCreate">+ Yangi</button>
    </header>

    <div :class="['debtors-summary', isPosMode ? 'debtors-summary--pos card' : 'card']">
      <div>
        <span class="debtors-summary__label">Jami qarz</span>
        <strong class="debtors-summary__value">{{ formatMoney(totalDebt) }} so‘m</strong>
      </div>
      <div class="debtors-summary__search">
        <input
          v-model="search"
          type="search"
          placeholder="Ism yoki telefon..."
          @keyup.enter="!isPosMode && fetchDebtors()"
        />
        <button
          v-if="!isPosMode"
          class="btn btn--ghost btn--sm"
          type="button"
          @click="fetchDebtors"
        >
          Qidirish
        </button>
      </div>
    </div>

    <!-- POS: karta ro‘yxati -->
    <div v-if="isPosMode" class="debtors-pos-list">
      <p v-if="loading" class="debtors-pos-empty">Yuklanmoqda...</p>
      <p v-else-if="!filteredRows.length" class="debtors-pos-empty">Qarzdorlar yo‘q</p>
      <article
        v-for="row in filteredRows"
        :key="row.id"
        class="debtors-pos-card"
      >
        <div class="debtors-pos-card__main">
          <strong class="debtors-pos-card__name">{{ row.name }}</strong>
          <small v-if="row.phone" class="debtors-pos-card__phone">{{ row.phone }}</small>
          <small v-if="row.note" class="debtors-pos-card__note">{{ row.note }}</small>
        </div>
        <div class="debtors-pos-card__debt">
          <span>Qarz</span>
          <strong :class="Number(row.balance_due) > 0 ? 'is-debt' : ''">
            {{ formatMoney(row.balance_due) }}
          </strong>
        </div>
        <button
          class="debtors-pos-card__pay"
          type="button"
          :disabled="!Number(row.balance_due)"
          @click="openPay(row)"
        >
          Pul kiritish
        </button>
      </article>
    </div>

    <!-- Admin: jadval + CRUD -->
    <DataTable
      v-else
      :columns="columns"
      :rows="rows"
      :loading="loading"
      empty-text="Qarzdorlar yo‘q."
    >
      <template #cell:balance_due="{ row }">
        <strong :class="Number(row.balance_due) > 0 ? 'debt-amount' : 'debt-zero'">
          {{ formatMoney(row.balance_due) }}
        </strong>
      </template>
      <template #actions="{ row }">
        <button
          class="icon-btn"
          type="button"
          :disabled="!Number(row.balance_due)"
          @click="openPay(row)"
        >
          Qarzni qoplash
        </button>
        <button class="icon-btn" type="button" @click="openEdit(row)">Tahrirlash</button>
        <button class="icon-btn icon-btn--danger" type="button" @click="removeDebtor(row)">
          O‘chirish
        </button>
      </template>
    </DataTable>

    <!-- Yangi qarzdor -->
    <AppModal
      :open="createOpen"
      title="Yangi qarzdor"
      :width="isPosMode ? '480px' : '440px'"
      @close="createOpen = false"
    >
      <div class="form-stack">
        <label class="field field--full">
          <span>Ism *</span>
          <input v-model="createForm.name" type="text" autocomplete="name" />
        </label>
        <label class="field field--full">
          <span>Telefon</span>
          <input v-model="createForm.phone" type="tel" autocomplete="tel" />
        </label>
        <label class="field field--full">
          <span>Izoh</span>
          <input v-model="createForm.note" type="text" />
        </label>
        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </div>
      <template #footer>
        <button class="btn btn--ghost" type="button" @click="createOpen = false">Bekor</button>
        <button class="btn btn--primary" type="button" :disabled="saving" @click="submitCreate">
          {{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
        </button>
      </template>
    </AppModal>

    <!-- Tahrirlash (admin) -->
    <AppModal :open="editOpen" title="Qarzdorni tahrirlash" width="440px" @close="editOpen = false">
      <div class="form-stack">
        <label class="field field--full">
          <span>Ism *</span>
          <input v-model="editForm.name" type="text" />
        </label>
        <label class="field field--full">
          <span>Telefon</span>
          <input v-model="editForm.phone" type="tel" />
        </label>
        <label class="field field--full">
          <span>Izoh</span>
          <input v-model="editForm.note" type="text" />
        </label>
        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </div>
      <template #footer>
        <button class="btn btn--ghost" type="button" @click="editOpen = false">Bekor</button>
        <button class="btn btn--primary" type="button" :disabled="saving" @click="submitEdit">
          {{ saving ? 'Saqlanmoqda...' : 'Yangilash' }}
        </button>
      </template>
    </AppModal>

    <!-- Pul kiritish -->
    <AppModal
      :open="payOpen"
      :title="selected ? `${selected.name} — pul kiritish` : 'Pul kiritish'"
      :width="isPosMode ? '480px' : '440px'"
      @close="payOpen = false"
    >
      <div v-if="selected" class="form-stack">
        <p class="pay-balance">
          Joriy qarz: <strong>{{ formatMoney(selected.balance_due) }} so‘m</strong>
        </p>
        <label class="field field--full">
          <span>Summa *</span>
          <input v-model="payForm.amount" type="number" min="0" step="0.01" />
        </label>
        <div class="quick-amounts">
          <button type="button" @click="fillFullPay">To‘liq qoplash</button>
        </div>
        <label class="field field--full">
          <span>To‘lov usuli</span>
          <select v-model="payForm.method">
            <option value="cash">Naqd</option>
            <option value="card">Karta</option>
            <option value="transfer">O‘tkazma</option>
          </select>
        </label>
        <label class="field field--full">
          <span>Izoh</span>
          <input v-model="payForm.note" type="text" />
        </label>
        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </div>
      <template #footer>
        <button class="btn btn--ghost" type="button" @click="payOpen = false">Bekor</button>
        <button class="btn btn--primary" type="button" :disabled="saving" @click="submitPay">
          {{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.debtors-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.debtors-summary--pos {
  border-radius: 14px;
  margin-bottom: 16px;
}

.debtors-summary__label {
  display: block;
  font-size: 0.85rem;
  color: var(--muted);
  margin-bottom: 4px;
}

.debtors-summary__value {
  font-size: 1.35rem;
  color: var(--danger, #c0392b);
}

.debtors-summary__search {
  display: flex;
  gap: 8px;
  align-items: center;
  flex: 1;
  min-width: 220px;
  max-width: 420px;
}

.debtors-summary__search input {
  flex: 1;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  padding: 9px 12px;
  background: var(--surface-soft);
}

.debtors-page--pos .debtors-summary__search input {
  padding: 12px 14px;
  font-size: 1rem;
  border-radius: 12px;
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

.debtors-pos-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.debtors-pos-empty {
  text-align: center;
  padding: 48px 16px;
  color: #64748b;
  font-size: 1rem;
}

.debtors-pos-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 16px;
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  gap: 12px 16px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
}

.debtors-pos-card__main {
  grid-column: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.debtors-pos-card__name {
  font-size: 1.08rem;
  font-weight: 600;
  color: #0f172a;
}

.debtors-pos-card__phone,
.debtors-pos-card__note {
  font-size: 0.88rem;
  color: #64748b;
}

.debtors-pos-card__debt {
  grid-column: 2;
  grid-row: 1;
  text-align: right;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.debtors-pos-card__debt span {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #94a3b8;
}

.debtors-pos-card__debt strong {
  font-size: 1.25rem;
  font-weight: 700;
  color: #64748b;
}

.debtors-pos-card__debt strong.is-debt {
  color: #dc2626;
}

.debtors-pos-card__pay {
  grid-column: 1 / -1;
  width: 100%;
  border: 0;
  border-radius: 12px;
  padding: 14px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  background: #16a34a;
  color: #fff;
  transition: opacity 0.15s ease;
}

.debtors-pos-card__pay:disabled {
  background: #e2e8f0;
  color: #94a3b8;
  cursor: not-allowed;
}

.debtors-pos-card__pay:not(:disabled):hover {
  background: #15803d;
}

.debt-amount {
  color: var(--danger, #c0392b);
}

.debt-zero {
  color: var(--muted);
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

.debtors-page--pos :deep(.field input),
.debtors-page--pos :deep(.field select) {
  font-size: 1rem;
  padding: 12px 14px;
}
</style>
