<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useApiNotify } from '../../composables/useApiNotify'
import providerService from '../../services/provider.service'

const route = useRoute()
const router = useRouter()
const { showApiError } = useApiNotify()

const org = ref(null)
const loading = ref(true)
const error = ref(null)
const orgId = computed(() => Number(route.params.id))

const planModal = ref(false)
const planForm = ref({ plan_code: 'pro', days: 30 })

const extendModal = ref(false)
const extendForm = ref({ days: 30 })

function fmtDate(s) {
  if (!s) return '—'
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return s
  return d.toLocaleDateString('uz-UZ', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function fmtMoney(n) {
  if (n == null) return '0'
  const num = typeof n === 'string' ? parseFloat(n) : n
  return num.toLocaleString('uz-UZ', { maximumFractionDigits: 0 })
}

function remainingDays(endsAt) {
  if (!endsAt) return null
  const end = new Date(endsAt).getTime()
  const now = Date.now()
  const diff = Math.ceil((end - now) / (1000 * 60 * 60 * 24))
  return diff
}

const staffRoles = ref([])
const roleDraft = ref({})
const roleSavingId = ref(null)
const memberRemovingId = ref(null)

function rolesForMember(member) {
  const list = [...staffRoles.value]
  if (member.role_code === 'owner' && !list.some((r) => r.code === 'owner')) {
    list.unshift({
      id: member.role_id,
      code: 'owner',
      name: member.role_name || 'Egasi (Owner)',
    })
  }
  return list
}

function syncRoleDrafts() {
  const next = {}
  for (const m of org.value?.members || []) {
    next[m.id] = m.role_id
  }
  roleDraft.value = next
}

async function loadStaffRoles() {
  staffRoles.value = await providerService.orgs.staffRoles(orgId.value)
}

async function load() {
  loading.value = true
  error.value = null
  try {
    org.value = await providerService.orgs.retrieve(orgId.value)
    await loadStaffRoles()
    syncRoleDrafts()
  } catch (err) {
    error.value = err.response?.data?.detail || err.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function saveMemberRole(member) {
  const roleId = roleDraft.value[member.id]
  if (!roleId || Number(roleId) === Number(member.role_id)) return
  roleSavingId.value = member.id
  try {
    await providerService.orgs.setMemberRole(orgId.value, {
      membership_id: member.id,
      role_id: Number(roleId),
      branch_id: member.branch ?? null,
    })
    await load()
  } catch (err) {
    showApiError(err)
    roleDraft.value[member.id] = member.role_id
  } finally {
    roleSavingId.value = null
  }
}

async function removeMember(member) {
  const label = member.user_full_name || member.user_phone || 'xodim'
  if (!confirm(`"${label}" ni tashkilotdan chiqarilsinmi?`)) return
  memberRemovingId.value = member.id
  try {
    await providerService.orgs.removeMember(orgId.value, member.id)
    await load()
  } catch (err) {
    showApiError(err)
  } finally {
    memberRemovingId.value = null
  }
}

async function deleteOrg() {
  if (!org.value) return
  if (
    !confirm(
      `"${org.value.name}" mijozini butunlay o‘chirishni tasdiqlaysizmi? Do‘kon, savdolar va akkaunt o‘chiriladi. Shu telefon bilan qayta ro‘yxatdan o‘tish mumkin.`,
    )
  )
    return
  try {
    await providerService.orgs.delete(org.value.id)
    router.push({ name: 'provider-mijozlar' })
  } catch (err) {
    showApiError(err)
  }
}

async function toggleActive() {
  if (!org.value) return
  const action = org.value.is_active ? 'suspend' : 'activate'
  if (org.value.is_active && !confirm(`"${org.value.name}" tashkilotini bloklaysizmi?`)) return
  try {
    await providerService.orgs[action](org.value.id)
    org.value.is_active = !org.value.is_active
  } catch (err) {
    showApiError(err)
  }
}

async function submitExtend() {
  try {
    await providerService.orgs.setRemainingDays(org.value.id, extendForm.value.days)
    extendModal.value = false
    await load()
  } catch (err) {
    showApiError(err)
  }
}

async function submitChangePlan() {
  try {
    await providerService.orgs.changePlan(
      org.value.id,
      planForm.value.plan_code,
      planForm.value.days,
    )
    planModal.value = false
    await load()
  } catch (err) {
    showApiError(err)
  }
}

async function impersonate() {
  if (!confirm(`"${org.value.name}" tashkilotiga owner sifatida kirasizmi? Sizning hozirgi sessiyangiz almashtiriladi.`)) return
  try {
    const data = await providerService.orgs.impersonate(org.value.id)
    localStorage.setItem('access_token', data.access)
    localStorage.setItem('refresh_token', data.refresh)
    localStorage.setItem('organization_id', String(data.organization_id))
    localStorage.removeItem('is_provider')
    window.location.replace(new URL('/app', window.location.href).href)
  } catch (err) {
    showApiError(err)
  }
}

const inviteModal = ref(false)
const inviteSubmitting = ref(false)
const inviteError = ref(null)
const inviteFieldErrors = ref({})
const inviteResult = ref(null)
const inviteForm = ref({
  phone: '',
  full_name: '',
  role_id: '',
  branch_id: '',
  password: '',
  password_confirm: '',
})

async function openInviteModal() {
  inviteResult.value = null
  inviteError.value = null
  inviteFieldErrors.value = {}
  inviteForm.value = {
    phone: '',
    full_name: '',
    role_id: '',
    branch_id: '',
    password: '',
    password_confirm: '',
  }
  try {
    if (!staffRoles.value.length) await loadStaffRoles()
  } catch (err) {
    showApiError(err)
    return
  }
  inviteModal.value = true
}

function closeInviteModal() {
  if (inviteSubmitting.value) return
  inviteModal.value = false
}

async function submitInviteStaff() {
  inviteSubmitting.value = true
  inviteError.value = null
  inviteFieldErrors.value = {}
  if (!inviteForm.value.role_id) {
    inviteFieldErrors.value.role_id = 'Rolni tanlang'
    inviteSubmitting.value = false
    return
  }
  const pwd = inviteForm.value.password
  const pwd2 = inviteForm.value.password_confirm
  if (!pwd || pwd.length < 8) {
    inviteFieldErrors.value.password = 'Parol kamida 8 belgi bo‘lsin'
    inviteSubmitting.value = false
    return
  }
  if (pwd !== pwd2) {
    inviteFieldErrors.value.password_confirm = 'Parollar mos emas'
    inviteSubmitting.value = false
    return
  }
  try {
    const payload = {
      phone: inviteForm.value.phone.trim(),
      full_name: inviteForm.value.full_name.trim(),
      role_id: Number(inviteForm.value.role_id),
      password: pwd,
      password_confirm: pwd2,
    }
    const bid = inviteForm.value.branch_id
    if (bid !== '' && bid != null) payload.branch_id = Number(bid)
    const res = await providerService.orgs.inviteStaff(orgId.value, payload)
    inviteModal.value = false
    inviteResult.value = res
    await load()
  } catch (err) {
    const d = err.response?.data
    if (d && typeof d === 'object') {
      if (d.detail)
        inviteError.value = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail)
      else {
        inviteError.value = 'Maydonlarni tekshiring'
        for (const [k, v] of Object.entries(d)) {
          inviteFieldErrors.value[k] = Array.isArray(v) ? v[0] : String(v)
        }
      }
    } else {
      inviteError.value = err.message || 'Xatolik'
    }
  } finally {
    inviteSubmitting.value = false
  }
}

function dismissInviteBanner() {
  inviteResult.value = null
}
</script>

<template>
  <div class="prov-page">
    <button class="prov-link-back" @click="router.push({ name: 'provider-mijozlar' })">
      &larr; Mijozlar ro‘yxatiga
    </button>

    <div v-if="loading" class="prov-empty">Yuklanmoqda...</div>
    <div v-else-if="error" class="prov-error">{{ error }}</div>
    <template v-else-if="org">
      <header class="prov-head">
        <div>
          <h1 class="prov-head__title">{{ org.name }}</h1>
          <div class="prov-head__meta">
            <span>{{ org.phone || 'telefon kiritilmagan' }}</span>
            <span>·</span>
            <span>{{ org.address || 'manzil kiritilmagan' }}</span>
            <span>·</span>
            <span>ID #{{ org.id }}</span>
          </div>
        </div>
        <div class="prov-head__actions">
          <span
            class="prov-badge"
            :class="org.is_active ? 'prov-badge--ok' : 'prov-badge--danger'"
          >
            {{ org.is_active ? 'Faol' : 'Bloklangan' }}
          </span>
          <button class="prov-btn prov-btn--ghost" @click="toggleActive">
            {{ org.is_active ? 'Bloklash' : 'Faollashtirish' }}
          </button>
          <button class="prov-btn prov-btn--ghost" @click="impersonate">
            Owner sifatida kirish
          </button>
          <button class="prov-btn prov-btn--ghost is-danger-text" type="button" @click="deleteOrg">
            Mijozni o‘chirish
          </button>
        </div>
      </header>

      <p v-if="inviteResult" class="prov-invite-banner">
        <template v-if="inviteResult.user_created && inviteResult.used_manual_password">
          Yangi akkaunt yaratildi. Mijoz <strong>siz kiritgan parol</strong> bilan tizimga kirishi mumkin.
        </template>
        <template v-else-if="inviteResult.user_created && inviteResult.temporary_password">
          Yangi akkaunt yaratildi. <strong>Vaqtinchalik parol</strong> (bir marta, mijozga bering):
          <code class="prov-invite-banner__pwd">{{ inviteResult.temporary_password }}</code>
        </template>
        <template v-else>
          Mavjud foydalanuvchi bu tashkilotga xodim sifatida ulandi.
        </template>
        <button type="button" class="prov-invite-banner__close" @click="dismissInviteBanner">×</button>
      </p>

      <section class="prov-grid">
        <article class="prov-card">
          <div class="prov-card__label">Joriy tarif</div>
          <div class="prov-card__value">{{ org.plan_name || '—' }}</div>
          <div class="prov-card__meta">
            <span v-if="org.subscription_status" class="prov-badge">{{ org.subscription_status }}</span>
          </div>
          <div class="prov-card__hint">
            Tugaydi: {{ fmtDate(org.subscription_ends_at) }}
            <template v-if="remainingDays(org.subscription_ends_at) != null">
              — hozir: {{ remainingDays(org.subscription_ends_at) }} kun qoldi
            </template>
          </div>
          <div class="prov-card__actions">
            <button
              class="prov-btn prov-btn--sm"
              @click="
                extendForm.days = Math.max(0, remainingDays(org.subscription_ends_at) ?? 0);
                extendModal = true
              "
            >
              Qolgan kunni o‘zgartirish
            </button>
            <button class="prov-btn prov-btn--sm prov-btn--ghost" @click="planModal = true">
              Tarifni o'zgartirish
            </button>
          </div>
        </article>

        <article class="prov-card">
          <div class="prov-card__label">Foydalanuvchilar / Filiallar</div>
          <div class="prov-card__value">{{ org.users_count }} / {{ org.branches_count }}</div>
          <div class="prov-card__hint">Faol membership va filial soni</div>
        </article>

        <article class="prov-card">
          <div class="prov-card__label">Mahsulotlar / Kategoriyalar</div>
          <div class="prov-card__value">{{ org.stats?.products || 0 }} / {{ org.stats?.categories || 0 }}</div>
        </article>

        <article class="prov-card">
          <div class="prov-card__label">Jami savdo</div>
          <div class="prov-card__value">{{ org.stats?.total_sales || 0 }}</div>
          <div class="prov-card__hint">{{ fmtMoney(org.stats?.total_amount) }} so'm</div>
        </article>
      </section>

      <section class="prov-section">
        <h2 class="prov-section__title">Obunalar tarixi</h2>
        <div class="prov-table-wrap">
          <table class="prov-table">
            <thead>
              <tr>
                <th>Tarif</th>
                <th>Boshlandi</th>
                <th>Tugaydi</th>
                <th>Holat</th>
                <th>Auto-yangilanish</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!org.subscriptions?.length">
                <td colspan="5" class="prov-table__empty">Obunalar topilmadi</td>
              </tr>
              <tr v-for="s in org.subscriptions" :key="s.id">
                <td>{{ s.plan_name || s.plan_code }}</td>
                <td>{{ fmtDate(s.starts_at) }}</td>
                <td>{{ fmtDate(s.ends_at) }}</td>
                <td><span class="prov-badge">{{ s.status }}</span></td>
                <td>{{ s.auto_renew ? 'Ha' : "Yo'q" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="prov-section">
        <div class="prov-section__head">
          <h2 class="prov-section__title">Xodimlar</h2>
          <button type="button" class="prov-btn prov-btn--sm" @click="openInviteModal">Xodim qo‘shish</button>
        </div>
        <p class="prov-section__hint">
          Rolni o‘zgartiring (admin, kassir, sotuvchi va boshqalar) yoki xodimni tashkilotdan chiqaring.
        </p>
        <div class="prov-table-wrap">
          <table class="prov-table">
            <thead>
              <tr>
                <th>F.I.O.</th>
                <th>Telefon</th>
                <th>Rol</th>
                <th>Holat</th>
                <th>Qo'shilgan</th>
                <th class="prov-table__th-actions">Amallar</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!org.members?.length">
                <td colspan="6" class="prov-table__empty">Xodimlar topilmadi</td>
              </tr>
              <tr v-for="m in org.members" :key="m.id">
                <td>
                  <span class="prov-cell-strong">{{ m.user_full_name || '—' }}</span>
                  <span v-if="m.role_code === 'owner'" class="prov-member-tag">Do‘kon egasi</span>
                </td>
                <td>{{ m.user_phone || '—' }}</td>
                <td>
                  <select v-model="roleDraft[m.id]" class="prov-input prov-input--inline">
                    <option v-for="r in rolesForMember(m)" :key="r.id" :value="r.id">
                      {{ r.name }} ({{ r.code }})
                    </option>
                  </select>
                </td>
                <td>
                  <span class="prov-badge" :class="m.is_active ? 'prov-badge--ok' : 'prov-badge--danger'">
                    {{ m.status }}
                  </span>
                </td>
                <td>{{ fmtDate(m.created_at) }}</td>
                <td class="prov-table__td-actions">
                  <div class="prov-member-actions">
                    <button
                      type="button"
                      class="prov-btn prov-btn--sm"
                      :disabled="roleSavingId === m.id || Number(roleDraft[m.id]) === Number(m.role_id)"
                      @click="saveMemberRole(m)"
                    >
                      {{ roleSavingId === m.id ? '...' : 'Saqlash' }}
                    </button>
                    <button
                      type="button"
                      class="prov-btn prov-btn--sm prov-btn--ghost is-danger-text"
                      :disabled="memberRemovingId === m.id"
                      @click="removeMember(m)"
                    >
                      Chiqarish
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Modals -->
      <div v-if="extendModal" class="prov-modal" @click.self="extendModal = false">
        <div class="prov-modal__card">
          <h3>Qolgan kunni o‘rnatish</h3>
          <label class="prov-field">
            <span>Yangi qolgan kun (0–730)</span>
            <input v-model.number="extendForm.days" type="number" min="0" max="730" class="prov-input" />
          </label>
          <div class="prov-modal__actions">
            <button class="prov-btn prov-btn--ghost" @click="extendModal = false">Bekor</button>
            <button class="prov-btn" @click="submitExtend">Saqlash</button>
          </div>
        </div>
      </div>

      <div v-if="planModal" class="prov-modal" @click.self="planModal = false">
        <div class="prov-modal__card">
          <h3>Tarifni o'zgartirish</h3>
          <label class="prov-field">
            <span>Tarif</span>
            <select v-model="planForm.plan_code" class="prov-input">
              <option value="lite">Lite</option>
              <option value="pro">Pro</option>
            </select>
          </label>
          <label class="prov-field">
            <span>Muddat (kun)</span>
            <input v-model.number="planForm.days" type="number" min="1" class="prov-input" />
          </label>
          <div class="prov-modal__actions">
            <button class="prov-btn prov-btn--ghost" @click="planModal = false">Bekor</button>
            <button class="prov-btn" @click="submitChangePlan">O'zgartirish</button>
          </div>
        </div>
      </div>

      <div v-if="inviteModal" class="prov-modal" @click.self="closeInviteModal">
        <div class="prov-modal__card prov-modal__card--wide">
          <h3>Xodim qo‘shish</h3>
          <p v-if="inviteError" class="prov-invite-error">{{ inviteError }}</p>
          <label class="prov-field">
            <span>Telefon (login) <span class="prov-req">*</span></span>
            <input v-model="inviteForm.phone" type="tel" class="prov-input" placeholder="+998..." />
            <span v-if="inviteFieldErrors.phone" class="prov-field-err">{{ inviteFieldErrors.phone }}</span>
          </label>
          <label class="prov-field">
            <span>Ism-familiya <span class="prov-req">*</span></span>
            <input v-model="inviteForm.full_name" type="text" class="prov-input" />
            <span v-if="inviteFieldErrors.full_name" class="prov-field-err">{{ inviteFieldErrors.full_name }}</span>
          </label>
          <label class="prov-field">
            <span>Rol <span class="prov-req">*</span></span>
            <select v-model="inviteForm.role_id" class="prov-input">
              <option disabled value="">Tanlang</option>
              <option v-for="r in staffRoles" :key="r.id" :value="r.id">{{ r.name }} ({{ r.code }})</option>
            </select>
            <span v-if="inviteFieldErrors.role_id" class="prov-field-err">{{ inviteFieldErrors.role_id }}</span>
          </label>
          <label class="prov-field">
            <span>Filial</span>
            <select v-model="inviteForm.branch_id" class="prov-input">
              <option value="">Filial tanlanmasin</option>
              <option v-for="b in org.branches || []" :key="b.id" :value="b.id">{{ b.name }}</option>
            </select>
            <span v-if="inviteFieldErrors.branch_id" class="prov-field-err">{{ inviteFieldErrors.branch_id }}</span>
          </label>
          <label class="prov-field">
            <span>Parol <span class="prov-req">*</span></span>
            <input
              v-model="inviteForm.password"
              type="password"
              class="prov-input"
              autocomplete="new-password"
              minlength="8"
            />
            <span v-if="inviteFieldErrors.password" class="prov-field-err">{{ inviteFieldErrors.password }}</span>
          </label>
          <label class="prov-field">
            <span>Parolni tasdiqlash <span class="prov-req">*</span></span>
            <input
              v-model="inviteForm.password_confirm"
              type="password"
              class="prov-input"
              autocomplete="new-password"
              minlength="8"
            />
            <span v-if="inviteFieldErrors.password_confirm" class="prov-field-err">{{
              inviteFieldErrors.password_confirm
            }}</span>
          </label>
          <div class="prov-modal__actions">
            <button type="button" class="prov-btn prov-btn--ghost" :disabled="inviteSubmitting" @click="closeInviteModal">
              Bekor
            </button>
            <button type="button" class="prov-btn" :disabled="inviteSubmitting" @click="submitInviteStaff">
              {{ inviteSubmitting ? 'Saqlanmoqda...' : 'Qo‘shish' }}
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.prov-link-back {
  background: transparent;
  border: 0;
  color: #94a3b8;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
  margin-bottom: 14px;
}
.prov-link-back:hover { color: #fff; }

.prov-empty {
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  color: #64748b;
}

.prov-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 22px;
}
.prov-head__title { margin: 0; font-size: 22px; font-weight: 700; color: #fff; }
.prov-head__meta {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 13px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.prov-head__actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }

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
  font-size: 24px;
  font-weight: 700;
  color: #fff;
  margin-top: 8px;
}
.prov-card__meta { display: flex; gap: 6px; margin-top: 8px; }
.prov-card__hint { margin-top: 8px; font-size: 12px; color: #64748b; }
.prov-card__actions { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }

.prov-section { margin-bottom: 22px; }
.prov-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.prov-section__title { margin: 0; font-size: 15px; font-weight: 600; color: #fff; }
.prov-section__hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.45;
}

.prov-invite-banner {
  position: relative;
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.35);
  color: #bbf7d0;
  padding: 12px 36px 12px 14px;
  border-radius: 10px;
  font-size: 13px;
  margin-bottom: 18px;
  line-height: 1.5;
}
.prov-invite-banner__pwd {
  display: inline-block;
  margin-left: 6px;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.25);
  color: #fff;
  font-size: 13px;
}
.prov-invite-banner__close {
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
.prov-invite-banner__close:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.06);
}

.prov-invite-error {
  margin: 0 0 12px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.12);
  color: #fecaca;
  font-size: 13px;
}
.prov-field-err {
  font-size: 12px;
  color: #f87171;
}
.prov-req { color: #fb923c; }

.prov-modal__card--wide {
  width: min(100%, 460px);
}
.prov-table-wrap {
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  overflow: auto;
}
.prov-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.prov-table th {
  text-align: left;
  padding: 11px 14px;
  color: #94a3b8;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  font-weight: 600;
}
.prov-table td {
  padding: 11px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  color: #e5e7eb;
}
.prov-table__empty { padding: 24px; text-align: center; color: #64748b; }

.prov-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
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
.prov-badge--ok { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.prov-badge--danger { background: rgba(239, 68, 68, 0.15); color: #f87171; }

.prov-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: #cbd5e1;
  font-size: 11px;
  font-weight: 600;
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
.prov-btn--ghost {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #cbd5e1;
}
.prov-btn--ghost:hover { background: rgba(255, 255, 255, 0.06); color: #fff; }
.prov-btn--sm { padding: 7px 12px; font-size: 12px; }

.prov-modal {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: grid; place-items: center;
  padding: 20px; z-index: 50;
}
.prov-modal__card {
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 24px;
  width: min(100%, 420px);
}
.prov-modal__card h3 { margin: 0 0 14px; color: #fff; font-size: 16px; }
.prov-field { display: block; margin-bottom: 12px; }
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
}
.prov-modal__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }

.is-danger-text {
  color: #f87171 !important;
}
.is-danger-text:hover {
  color: #fecaca !important;
  background: rgba(239, 68, 68, 0.1) !important;
}

.prov-cell-strong {
  display: block;
  font-weight: 600;
  color: #fff;
}
.prov-member-tag {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #94a3b8;
}
.prov-input--inline {
  min-width: 160px;
  max-width: 220px;
  padding: 7px 10px;
  font-size: 12px;
}
.prov-table__th-actions {
  width: 140px;
  text-align: right;
}
.prov-table__td-actions {
  text-align: right;
  vertical-align: middle;
}
.prov-member-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
</style>
