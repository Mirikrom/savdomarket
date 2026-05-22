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

const bootstrapOpen = ref(false)
const bootstrapSubmitting = ref(false)
const bootstrapError = ref(null)
const bootstrapFieldErrors = ref({})
const bootstrapSuccess = ref(null)
const bootstrapForm = ref({
  organization_name: '',
  full_name: '',
  phone: '',
  email: '',
  password: '',
})
const bootstrapPwd2 = ref('')

const filtered = computed(() => items.value)

function fmtDate(s) {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  return d.toLocaleDateString('uz-UZ', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

let debounceTimer = null

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
  router.push({ name: 'provider-org-detail', params: { id: String(org.id) } })
}

async function deleteOrg(org) {
  if (
    !confirm(
      `"${org.name}" mijozini butunlay o‘chirishni tasdiqlaysizmi? Do‘kon, mahsulotlar, savdolar va akkaunt o‘chiriladi. Shu telefon bilan qayta ro‘yxatdan o‘tish mumkin.`,
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

function resetBootstrapForm() {
  bootstrapForm.value = {
    organization_name: '',
    full_name: '',
    phone: '',
    email: '',
    password: '',
  }
  bootstrapPwd2.value = ''
  bootstrapError.value = null
  bootstrapFieldErrors.value = {}
  bootstrapSuccess.value = null
}

function openBootstrap() {
  bootstrapSuccess.value = null
  resetBootstrapForm()
  bootstrapOpen.value = true
}

function closeBootstrap() {
  if (bootstrapSubmitting.value) return
  bootstrapOpen.value = false
}

function applyBootstrapErrors(data) {
  bootstrapFieldErrors.value = {}
  if (!data || typeof data !== 'object') {
    bootstrapError.value = typeof data === 'string' ? data : "So'rovda xato"
    return
  }
  if (data.detail) {
    bootstrapError.value =
      typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    return
  }
  bootstrapError.value = 'Maydonlarni tekshiring'
  for (const [k, v] of Object.entries(data)) {
    bootstrapFieldErrors.value[k] = Array.isArray(v) ? v[0] : String(v)
  }
}

async function submitBootstrap() {
  bootstrapSubmitting.value = true
  bootstrapError.value = null
  bootstrapFieldErrors.value = {}
  bootstrapSuccess.value = null

  if (bootstrapForm.value.password !== bootstrapPwd2.value) {
    bootstrapFieldErrors.value.password_confirm = 'Parollar mos emas'
    bootstrapSubmitting.value = false
    return
  }

  try {
    const res = await providerService.users.bootstrapClient({
      organization_name: bootstrapForm.value.organization_name.trim(),
      full_name: bootstrapForm.value.full_name.trim(),
      phone: bootstrapForm.value.phone.trim(),
      email: (bootstrapForm.value.email || '').trim(),
      password: bootstrapForm.value.password,
    })
    bootstrapSuccess.value = res
    bootstrapOpen.value = false
    await load()
  } catch (err) {
    applyBootstrapErrors(err.response?.data)
  } finally {
    bootstrapSubmitting.value = false
  }
}
</script>

<template>
  <div class="prov-page">
    <header class="prov-page__header prov-page__header--row">
      <div>
        <h1 class="prov-page__title">Mijozlar</h1>
        <p class="prov-page__subtitle">
          Har qator — bitta do‘kon va uning egasi. Batafsil va xodimlar uchun qatorni bosing.
        </p>
      </div>
      <button type="button" class="prov-btn" @click="openBootstrap">Yangi mijoz (do‘kon + login)</button>
    </header>

    <p v-if="bootstrapSuccess" class="prov-success-banner">
      <strong>Yaratildi:</strong>
      {{ bootstrapSuccess.organization?.name }} — login:
      {{ bootstrapSuccess.user?.phone }}.
      <span class="prov-success-banner__hint">Parolni mijozga xavfsiz yo‘llang.</span>
      <button type="button" class="prov-success-banner__dismiss" @click="bootstrapSuccess = null">
        ×
      </button>
    </p>

    <section class="prov-filters">
      <input
        v-model="search"
        type="search"
        class="prov-input"
        placeholder="Do‘kon, egachi telefon / ismi..."
      />
      <select v-model="plan" class="prov-input">
        <option value="">Barcha tariflar</option>
        <option value="lite">Lite</option>
        <option value="pro">Pro</option>
      </select>
      <select v-model="active" class="prov-input">
        <option value="">Holat: barcha</option>
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
            <th>Do‘kon admini</th>
            <th>Telefon</th>
            <th>Do‘kon</th>
            <th>Oxirgi aktivlik</th>
            <th>Xodimlar</th>
            <th>Tarif</th>
            <th>Holat</th>
            <th class="prov-table__th-actions">Amallar</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="8" class="prov-table__empty">Yuklanmoqda...</td>
          </tr>
          <tr v-else-if="!filtered.length">
            <td colspan="8" class="prov-table__empty">Mijoz topilmadi</td>
          </tr>
          <tr
            v-for="org in filtered"
            :key="org.id"
            class="prov-table__row prov-table__row--click"
            @click="openDetail(org)"
          >
            <td>
              <span class="prov-cell-strong">{{ org.owner_full_name || '—' }}</span>
            </td>
            <td>{{ org.owner_phone || '—' }}</td>
            <td>
              <span class="prov-cell-strong">{{ org.name }}</span>
            </td>
            <td>{{ fmtDate(org.last_activity_at || org.last_sale_at) }}</td>
            <td>{{ org.staff_count ?? 0 }}</td>
            <td>
              <span v-if="org.plan_code" class="prov-pill" :class="`is-${org.plan_code}`">
                {{ org.plan_name || org.plan_code }}
              </span>
              <span v-else class="prov-pill is-none">—</span>
            </td>
            <td>
              <span class="prov-badge" :class="org.is_active ? 'prov-badge--ok' : 'prov-badge--danger'">
                {{ org.is_active ? 'Faol' : 'Bloklangan' }}
              </span>
            </td>
            <td class="prov-table__td-actions" @click.stop>
              <div class="prov-actions" role="group" aria-label="Mijoz amallari">
                <button
                  class="prov-btn-icon"
                  type="button"
                  title="Batafsil"
                  @click="openDetail(org)"
                >
                  <svg class="prov-btn-icon__svg" viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      fill="none"
                      stroke="currentColor"
                      stroke-width="2"
                      stroke-linecap="round"
                      d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"
                    />
                    <circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="2" />
                  </svg>
                </button>
                <button
                  class="prov-btn-icon is-danger"
                  type="button"
                  title="Mijozni o‘chirish"
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
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <AppModal
      :open="bootstrapOpen"
      title="Yangi mijoz: do'kon + foydalanuvchi"
      width="520px"
      @close="closeBootstrap"
    >
      <p class="prov-modal-lead">
        Yangi <strong>tashkilot</strong>, uning <strong>egasi</strong> va kirish <strong>paroli</strong>.
      </p>
      <p v-if="bootstrapError" class="prov-inline-error">{{ bootstrapError }}</p>
      <form id="prov-bootstrap-form" class="prov-bootstrap-form" @submit.prevent="submitBootstrap">
        <label class="prov-field">
          <span>Do‘kon / tashkilot nomi <span class="prov-req">*</span></span>
          <input
            v-model="bootstrapForm.organization_name"
            type="text"
            class="prov-input"
            required
            maxlength="255"
            autocomplete="organization"
          />
          <span v-if="bootstrapFieldErrors.organization_name" class="prov-field-error">{{
            bootstrapFieldErrors.organization_name
          }}</span>
        </label>
        <label class="prov-field">
          <span>Ism-familiya (egasi) <span class="prov-req">*</span></span>
          <input
            v-model="bootstrapForm.full_name"
            type="text"
            class="prov-input"
            required
            maxlength="255"
            autocomplete="name"
          />
          <span v-if="bootstrapFieldErrors.full_name" class="prov-field-error">{{
            bootstrapFieldErrors.full_name
          }}</span>
        </label>
        <label class="prov-field">
          <span>Telefon (login) <span class="prov-req">*</span></span>
          <input
            v-model="bootstrapForm.phone"
            type="tel"
            class="prov-input"
            required
            maxlength="20"
            placeholder="+998..."
            autocomplete="tel"
          />
          <span v-if="bootstrapFieldErrors.phone" class="prov-field-error">{{ bootstrapFieldErrors.phone }}</span>
        </label>
        <label class="prov-field">
          <span>Email</span>
          <input
            v-model="bootstrapForm.email"
            type="email"
            class="prov-input"
            maxlength="254"
            autocomplete="email"
          />
          <span v-if="bootstrapFieldErrors.email" class="prov-field-error">{{ bootstrapFieldErrors.email }}</span>
        </label>
        <label class="prov-field">
          <span>Parol <span class="prov-req">*</span></span>
          <input
            v-model="bootstrapForm.password"
            type="password"
            class="prov-input"
            required
            minlength="8"
            autocomplete="new-password"
          />
          <span v-if="bootstrapFieldErrors.password" class="prov-field-error">{{
            bootstrapFieldErrors.password
          }}</span>
        </label>
        <label class="prov-field">
          <span>Parolni tasdiqlash <span class="prov-req">*</span></span>
          <input
            v-model="bootstrapPwd2"
            type="password"
            class="prov-input"
            required
            minlength="8"
            autocomplete="new-password"
          />
          <span v-if="bootstrapFieldErrors.password_confirm" class="prov-field-error">{{
            bootstrapFieldErrors.password_confirm
          }}</span>
        </label>
      </form>
      <template #footer>
        <button type="button" class="prov-btn prov-btn--ghost" :disabled="bootstrapSubmitting" @click="closeBootstrap">
          Bekor
        </button>
        <button type="submit" form="prov-bootstrap-form" class="prov-btn" :disabled="bootstrapSubmitting">
          {{ bootstrapSubmitting ? 'Yaratilmoqda...' : 'Yaratish' }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.prov-page__header {
  margin-bottom: 16px;
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

.prov-success-banner {
  position: relative;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  color: #bbf7d0;
  padding: 12px 36px 12px 14px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 12px;
  line-height: 1.45;
}
.prov-success-banner__hint {
  display: block;
  margin-top: 4px;
  color: #94a3b8;
  font-size: 12px;
}
.prov-success-banner__dismiss {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
}
.prov-success-banner__dismiss:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.06);
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
.prov-table__row--click {
  cursor: pointer;
  transition: background 0.12s;
}
.prov-table__row--click:hover {
  background: rgba(255, 255, 255, 0.04);
}
.prov-table__empty {
  padding: 28px;
  text-align: center;
  color: #64748b;
}

.prov-cell-strong {
  font-weight: 600;
  color: #fff;
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

.prov-badge {
  display: inline-flex;
  padding: 3px 9px;
  border-radius: 999px;
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

.prov-modal-lead {
  margin: 0 0 14px;
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.5;
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
.prov-bootstrap-form {
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
.prov-req {
  color: #f97316;
}
.prov-field-error {
  font-size: 12px;
  color: #f87171;
}

.prov-table__th-actions {
  width: 100px;
  text-align: right;
}
.prov-table__td-actions {
  text-align: right;
  vertical-align: middle;
}
.prov-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}
.prov-btn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.04);
  color: #cbd5e1;
  cursor: pointer;
}
.prov-btn-icon__svg {
  width: 18px;
  height: 18px;
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
}

@media (max-width: 900px) {
  .prov-filters {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
