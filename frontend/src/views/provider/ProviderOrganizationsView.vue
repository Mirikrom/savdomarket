<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import AppModal from '../../components/AppModal.vue'
import { useApiNotify } from '../../composables/useApiNotify'
import providerService from '../../services/provider.service'

const router = useRouter()
const { showApiError } = useApiNotify()

const items = ref([])
const loading = ref(false)
const error = ref(null)

const search = ref('')
const plan = ref('')
const active = ref('')
const subStatus = ref('')

const orgModalOpen = ref(false)
const editingId = ref(null)
const formSubmitting = ref(false)
const formError = ref(null)
const formFieldErrors = ref({})
const orgForm = ref({
  name: '',
  slug: '',
  phone: '',
  address: '',
  is_active: true,
})

let debounceTimer = null

const filtered = computed(() => items.value)

function fmtDate(s) {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  return d.toLocaleDateString('uz-UZ', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function daysLeft(endsAt) {
  if (!endsAt) return null
  const end = new Date(endsAt).getTime()
  const now = Date.now()
  const days = Math.ceil((end - now) / (1000 * 60 * 60 * 24))
  return days
}

async function load() {
  loading.value = true
  error.value = null
  try {
    const params = {}
    if (search.value.trim()) params.search = search.value.trim()
    if (plan.value) params.plan = plan.value
    if (active.value) params.active = active.value
    if (subStatus.value) params.sub_status = subStatus.value
    items.value = await providerService.orgs.list(params)
  } catch (err) {
    error.value = err.response?.data?.detail || err.message
    items.value = []
  } finally {
    loading.value = false
  }
}

function reloadSoon() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(load, 250)
}

watch([search, plan, active, subStatus], reloadSoon)

onMounted(load)

function openDetail(org) {
  router.push(`/provider/orgs/${org.id}`)
}

function resetOrgForm() {
  orgForm.value = {
    name: '',
    slug: '',
    phone: '',
    address: '',
    is_active: true,
  }
  formError.value = null
  formFieldErrors.value = {}
}

function openCreate() {
  editingId.value = null
  resetOrgForm()
  orgModalOpen.value = true
}

function openEdit(org) {
  editingId.value = org.id
  orgForm.value = {
    name: org.name || '',
    slug: org.slug || '',
    phone: org.phone || '',
    address: org.address || '',
    is_active: Boolean(org.is_active),
  }
  formError.value = null
  formFieldErrors.value = {}
  orgModalOpen.value = true
}

function closeOrgModal() {
  if (formSubmitting.value) return
  orgModalOpen.value = false
}

function applyApiErrors(data) {
  formFieldErrors.value = {}
  if (!data || typeof data !== 'object') {
    formError.value = typeof data === 'string' ? data : "So'rovda xato"
    return
  }
  if (data.detail) {
    formError.value =
      typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    return
  }
  formError.value = 'Maydonlarni tekshiring'
  for (const [k, v] of Object.entries(data)) {
    formFieldErrors.value[k] = Array.isArray(v) ? v[0] : String(v)
  }
}

async function submitOrgForm() {
  formSubmitting.value = true
  formError.value = null
  formFieldErrors.value = {}
  const payload = {
    name: orgForm.value.name.trim(),
    slug: (orgForm.value.slug || '').trim(),
    phone: (orgForm.value.phone || '').trim(),
    address: (orgForm.value.address || '').trim(),
    is_active: orgForm.value.is_active,
  }
  if (!payload.name) {
    formError.value = 'Nom bo‘sh bo‘lmasligi kerak'
    formSubmitting.value = false
    return
  }
  try {
    if (editingId.value) {
      await providerService.orgs.patch(editingId.value, payload)
    } else {
      await providerService.orgs.create(payload)
    }
    orgModalOpen.value = false
    await load()
  } catch (err) {
    applyApiErrors(err.response?.data)
  } finally {
    formSubmitting.value = false
  }
}

async function deleteOrg(org) {
  if (
    !confirm(
      `"${org.name}" mijozini butunlay o‘chirishni tasdiqlaysizmi? Barcha ma’lumotlar va akkaunt o‘chiriladi. Shu telefon bilan qayta ro‘yxatdan o‘tish mumkin.`,
    )
  )
    return
  try {
    await providerService.orgs.delete(org.id)
    await load()
  } catch (err) {
    showApiError(err)
  }
}

async function quickSuspend(org) {
  if (!confirm(`"${org.name}" tashkilotini bloklaysizmi?`)) return
  try {
    await providerService.orgs.suspend(org.id)
    org.is_active = false
  } catch (err) {
    showApiError(err)
  }
}

async function quickActivate(org) {
  try {
    await providerService.orgs.activate(org.id)
    org.is_active = true
  } catch (err) {
    showApiError(err)
  }
}

async function quickExtend(org) {
  const ans = prompt('Trial necha kunga uzaytiriladi?', '30')
  if (!ans) return
  const days = parseInt(ans, 10)
  if (!days || days < 1) return
  try {
    const res = await providerService.orgs.extendTrial(org.id, days)
    org.subscription_ends_at = res.ends_at
    org.subscription_status = res.status
  } catch (err) {
    showApiError(err)
  }
}
</script>

<template>
  <div class="prov-page">
    <header class="prov-page__header prov-page__header--row">
      <div>
        <h1 class="prov-page__title">Tashkilotlar</h1>
        <p class="prov-page__subtitle">Platforma mijozlari ro'yxati</p>
      </div>
      <button type="button" class="btn btn--primary" @click="openCreate">Yangi tashkilot</button>
    </header>

    <section class="prov-filters">
      <input
        v-model="search"
        type="search"
        class="prov-input"
        placeholder="Qidirish: nom, telefon, slug..."
      />
      <select v-model="plan" class="prov-input">
        <option value="">Barcha tariflar</option>
        <option value="lite">Lite</option>
        <option value="pro">Pro</option>
      </select>
      <select v-model="active" class="prov-input">
        <option value="">Barcha holatlar</option>
        <option value="1">Faol</option>
        <option value="0">Bloklangan</option>
      </select>
      <select v-model="subStatus" class="prov-input">
        <option value="">Obuna holati: barcha</option>
        <option value="active">Active</option>
        <option value="grace">Grace</option>
        <option value="expired">Expired</option>
        <option value="canceled">Canceled</option>
      </select>
    </section>

    <p v-if="error" class="prov-error">{{ error }}</p>

    <div class="prov-table-wrap">
      <table class="prov-table">
        <thead>
          <tr>
            <th>Tashkilot</th>
            <th>Tarif</th>
            <th>Obuna</th>
            <th>F./M.</th>
            <th>Mahsulot</th>
            <th>Oxirgi savdo</th>
            <th>Holat</th>
            <th class="prov-table__th-actions">Amallar</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="prov-table__empty">Yuklanmoqda...</td>
          </tr>
          <tr v-else-if="!filtered.length">
            <td colspan="8" class="prov-table__empty">Tashkilot topilmadi</td>
          </tr>
          <tr
            v-for="org in filtered"
            :key="org.id"
            @click="openDetail(org)"
            class="prov-table__row"
          >
            <td>
              <div class="prov-cell-org">
                <div class="prov-cell-org__name">{{ org.name }}</div>
                <div class="prov-cell-org__meta">{{ org.phone || '—' }} · {{ fmtDate(org.created_at) }}</div>
              </div>
            </td>
            <td>
              <span v-if="org.plan_code" class="prov-pill" :class="`is-${org.plan_code}`">
                {{ org.plan_name || org.plan_code }}
              </span>
              <span v-else class="prov-pill is-none">Yo'q</span>
            </td>
            <td>
              <div v-if="org.subscription_ends_at" class="prov-sub">
                <div class="prov-sub__date">{{ fmtDate(org.subscription_ends_at) }}</div>
                <div class="prov-sub__days" :class="{ 'is-warn': daysLeft(org.subscription_ends_at) < 7 }">
                  {{ daysLeft(org.subscription_ends_at) >= 0 ? `${daysLeft(org.subscription_ends_at)} kun` : 'tugagan' }}
                </div>
              </div>
              <span v-else class="prov-cell-muted">—</span>
            </td>
            <td>{{ org.users_count }} / {{ org.branches_count }}</td>
            <td>{{ org.products_count }}</td>
            <td>{{ fmtDate(org.last_sale_at) }}</td>
            <td>
              <span class="prov-badge" :class="org.is_active ? 'prov-badge--ok' : 'prov-badge--danger'">
                {{ org.is_active ? 'Faol' : 'Bloklangan' }}
              </span>
            </td>
            <td class="prov-table__td-actions" @click.stop>
              <div class="prov-actions" role="group" aria-label="Tashkilot amallari">
                <button class="prov-btn-icon" type="button" title="Tahrirlash" @click="openEdit(org)">
                  <svg class="prov-btn-icon__svg" viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"
                    />
                  </svg>
                </button>
                <button
                  class="prov-btn-icon is-danger"
                  type="button"
                  title="Butunlay o‘chirish"
                  @click="deleteOrg(org)"
                >
                  <svg class="prov-btn-icon__svg" viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6"
                    />
                  </svg>
                </button>
                <button
                  class="prov-btn-icon"
                  type="button"
                  title="Trial muddatini uzaytirish"
                  @click="quickExtend(org)"
                >
                  <svg class="prov-btn-icon__svg" viewBox="0 0 24 24" aria-hidden="true">
                    <rect
                      x="3"
                      y="4"
                      width="18"
                      height="18"
                      rx="2"
                      ry="2"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                    />
                    <path
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      d="M16 2v4M8 2v4M3 10h18"
                    />
                    <path
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      d="M12 14v4M10 16h4"
                    />
                  </svg>
                </button>
                <button
                  v-if="org.is_active"
                  class="prov-btn-icon is-warn"
                  type="button"
                  title="Bloklash"
                  @click="quickSuspend(org)"
                >
                  <svg class="prov-btn-icon__svg" viewBox="0 0 24 24" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" />
                    <path
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      d="M4.93 4.93l14.14 14.14"
                    />
                  </svg>
                </button>
                <button
                  v-else
                  class="prov-btn-icon is-ok"
                  type="button"
                  title="Faollashtirish"
                  @click="quickActivate(org)"
                >
                  <svg class="prov-btn-icon__svg" viewBox="0 0 24 24" aria-hidden="true">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" />
                    <path
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      d="M8 12l3 3 5-5"
                    />
                  </svg>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AppModal
      :open="orgModalOpen"
      :title="editingId ? 'Tashkilotni tahrirlash' : 'Yangi tashkilot'"
      width="520px"
      @close="closeOrgModal"
    >
      <p v-if="formError" class="prov-inline-error">{{ formError }}</p>
      <form id="prov-org-form" class="prov-org-modal-form" @submit.prevent="submitOrgForm">
        <label class="prov-field">
          <span>Nomi <span class="prov-req">*</span></span>
          <input v-model="orgForm.name" type="text" class="prov-input" required maxlength="255" />
          <span v-if="formFieldErrors.name" class="prov-field-error">{{ formFieldErrors.name }}</span>
        </label>
        <label class="prov-field">
          <span>Slug</span>
          <input v-model="orgForm.slug" type="text" class="prov-input" maxlength="80" placeholder="Bo'sh qoldiring — avtomatik" />
          <span v-if="formFieldErrors.slug" class="prov-field-error">{{ formFieldErrors.slug }}</span>
        </label>
        <label class="prov-field">
          <span>Telefon</span>
          <input v-model="orgForm.phone" type="text" class="prov-input" maxlength="20" />
          <span v-if="formFieldErrors.phone" class="prov-field-error">{{ formFieldErrors.phone }}</span>
        </label>
        <label class="prov-field">
          <span>Manzil</span>
          <input v-model="orgForm.address" type="text" class="prov-input" maxlength="255" />
          <span v-if="formFieldErrors.address" class="prov-field-error">{{ formFieldErrors.address }}</span>
        </label>
        <label class="prov-field prov-field--check">
          <input v-model="orgForm.is_active" type="checkbox" />
          <span>Faol</span>
        </label>
      </form>
      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="formSubmitting" @click="closeOrgModal">
          Bekor
        </button>
        <button type="submit" form="prov-org-form" class="btn btn--primary" :disabled="formSubmitting">
          {{ formSubmitting ? 'Saqlanmoqda...' : editingId ? 'Yangilash' : 'Yaratish' }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.prov-page__header {
  margin-bottom: 18px;
}
.prov-page__header--row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
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

.prov-filters {
  display: grid;
  grid-template-columns: 1.5fr 1fr 1fr 1fr;
  gap: 10px;
  margin-bottom: 16px;
}
.prov-input {
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 9px;
  font-size: 13px;
  outline: none;
  width: 100%;
  box-sizing: border-box;
}
.prov-input:focus {
  border-color: #f97316;
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

.prov-inline-error {
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #fecaca;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  margin: 0 0 12px;
}

.prov-org-modal-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.prov-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #cbd5e1;
}
.prov-field span:first-child {
  font-weight: 500;
  color: #e5e7eb;
}
.prov-field--check {
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
.prov-field--check input {
  width: auto;
}
.prov-req {
  color: #f97316;
}
.prov-field-error {
  font-size: 12px;
  color: #f87171;
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
  background: rgba(255, 255, 255, 0.02);
  font-weight: 600;
}
.prov-table__th-actions {
  text-align: right;
  white-space: nowrap;
  min-width: 188px;
}
.prov-table__td-actions {
  white-space: nowrap;
  vertical-align: middle;
  min-width: 188px;
  text-align: right;
}
.prov-table td {
  padding: 12px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  color: #e5e7eb;
  vertical-align: middle;
}
.prov-table__row {
  cursor: pointer;
  transition: background 0.12s;
}
.prov-table__row:hover {
  background: rgba(255, 255, 255, 0.03);
}
.prov-table__empty {
  padding: 28px;
  text-align: center;
  color: #64748b;
}

.prov-cell-org__name {
  font-weight: 600;
  color: #fff;
}
.prov-cell-org__meta {
  color: #94a3b8;
  font-size: 12px;
  margin-top: 2px;
}
.prov-cell-muted {
  color: #64748b;
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
.prov-pill.is-none {
  color: #64748b;
}

.prov-sub__date {
  color: #fff;
}
.prov-sub__days {
  color: #94a3b8;
  font-size: 11px;
}
.prov-sub__days.is-warn {
  color: #facc15;
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
.prov-badge--danger {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.prov-actions {
  display: inline-flex;
  flex-direction: row;
  flex-wrap: nowrap;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}
.prov-btn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: #cbd5e1;
  cursor: pointer;
  line-height: 0;
}
.prov-btn-icon__svg {
  width: 18px;
  height: 18px;
  display: block;
}
.prov-btn-icon:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #fff;
}
.prov-btn-icon.is-danger {
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.35);
}
.prov-btn-icon.is-danger:hover {
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
}
.prov-btn-icon.is-warn {
  color: #fbbf24;
  border-color: rgba(251, 191, 36, 0.4);
}
.prov-btn-icon.is-warn:hover {
  background: rgba(251, 191, 36, 0.1);
  color: #fde68a;
}
.prov-btn-icon.is-ok {
  color: #4ade80;
  border-color: rgba(34, 197, 94, 0.35);
}
.prov-btn-icon.is-ok:hover {
  background: rgba(34, 197, 94, 0.12);
  color: #bbf7d0;
}

@media (max-width: 900px) {
  .prov-filters {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .prov-filters {
    grid-template-columns: 1fr;
  }
}
</style>
