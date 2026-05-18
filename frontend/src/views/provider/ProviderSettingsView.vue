<script setup>
import { reactive, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'

import AppModal from '../../components/AppModal.vue'
import { useAuthStore } from '../../stores/auth'
import { logout as logoutService } from '../../services/auth.service'
import providerService from '../../services/provider.service'

const router = useRouter()
const auth = useAuthStore()

const pwdModalOpen = ref(false)
const pwd = reactive({
  old_password: '',
  new_password: '',
  new_password_confirm: '',
})
const pwdSubmitting = ref(false)
const pwdError = ref('')
const pwdFieldErrors = ref({})

const shortcuts = [
  { to: { name: 'provider-dashboard' }, label: 'Bosh sahifa', desc: 'Statistika va umumiy ko‘rinish' },
  { to: { name: 'provider-orgs' }, label: 'Tashkilotlar', desc: 'Mijoz do‘konlari, obuna, trial' },
  { to: { name: 'provider-mijozlar' }, label: 'Mijozlar', desc: 'Do‘kon egasi va xodimlar — batafsil sahifa' },
  { to: { name: 'provider-plans' }, label: 'Tariflar', desc: 'Lite / Pro cheklovlari va narxlar' },
]

function clearPwdMessages() {
  pwdError.value = ''
  pwdFieldErrors.value = {}
}

function resetPwdForm() {
  pwd.old_password = ''
  pwd.new_password = ''
  pwd.new_password_confirm = ''
  clearPwdMessages()
}

function openPwdModal() {
  resetPwdForm()
  pwdModalOpen.value = true
}

function closePwdModal() {
  pwdModalOpen.value = false
  resetPwdForm()
}

async function submitPassword() {
  clearPwdMessages()
  pwdSubmitting.value = true
  try {
    await providerService.changePassword({
      old_password: pwd.old_password,
      new_password: pwd.new_password,
      new_password_confirm: pwd.new_password_confirm,
    })
    pwd.old_password = ''
    pwd.new_password = ''
    pwd.new_password_confirm = ''
    try {
      await logoutService()
    } catch {
      /* ignore */
    }
    auth.reset()
    router.push({ name: 'login', query: { password_changed: '1' } })
  } catch (err) {
    const d = err.response?.data
    if (d && typeof d === 'object') {
      pwdFieldErrors.value = {
        old_password: Array.isArray(d.old_password) ? d.old_password[0] : d.old_password,
        new_password: Array.isArray(d.new_password) ? d.new_password.join(' ') : d.new_password,
        new_password_confirm: Array.isArray(d.new_password_confirm)
          ? d.new_password_confirm[0]
          : d.new_password_confirm,
      }
      pwdError.value = typeof d.detail === 'string' ? d.detail : ''
      if (!pwdError.value && d.non_field_errors?.length) {
        pwdError.value = d.non_field_errors.join(' ')
      }
      if (!pwdError.value && !Object.values(pwdFieldErrors.value).some(Boolean)) {
        pwdError.value = err.message || 'Xatolik yuz berdi.'
      }
    } else {
      pwdError.value = err.message || 'Xatolik yuz berdi.'
    }
  } finally {
    pwdSubmitting.value = false
  }
}
</script>

<template>
  <div class="prov-page">
    <header class="prov-page__header">
      <div>
        <h1 class="prov-page__title">Sozlamalar</h1>
        <p class="prov-page__subtitle">
          Super admin akkaunti — parol va tezkor havolalar
        </p>
      </div>
    </header>

    <section class="prov-account-strip" v-if="auth.user">
      <span class="prov-account-strip__label">Joriy kirish</span>
      <span class="prov-account-strip__phone">{{ auth.user.phone || '—' }}</span>
      <span v-if="auth.user.full_name" class="prov-account-strip__name">{{ auth.user.full_name }}</span>
    </section>

    <section class="prov-pwd-cta" aria-label="Hisob-xavfsizligi">
      <div class="prov-pwd-cta__icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
          <rect x="5" y="11" width="14" height="10" rx="2" />
          <path d="M12 15v2M8 11V7a4 4 0 0 1 8 0v4" />
        </svg>
      </div>
      <div class="prov-pwd-cta__text">
        <span class="prov-pwd-cta__title">Parolni yangilash</span>
        <span class="prov-pwd-cta__desc">Yangi parol saqlangach tizimdan chiqarilasiz va qayta kirasiz</span>
      </div>
      <button type="button" class="prov-pwd-cta__btn" @click="openPwdModal">Parolni o‘zgartirish</button>
    </section>

    <section class="prov-shortcuts" aria-label="Tezkor havolalar">
      <h2 class="prov-shortcuts__title">Tezkor havolalar</h2>
      <ul class="prov-shortcuts__grid">
        <li v-for="item in shortcuts" :key="item.label">
          <RouterLink :to="item.to" class="prov-shortcut-card">
            <span class="prov-shortcut-card__label">{{ item.label }}</span>
            <span class="prov-shortcut-card__desc">{{ item.desc }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>

    <AppModal
      :open="pwdModalOpen"
      title="Parolni yangilash"
      width="440px"
      @close="closePwdModal"
    >
      <p class="prov-modal-lead">
        <strong>{{ auth.user?.phone || '—' }}</strong> · yangi parol saqlangach tizimdan avtomatik chiqarilasiz va
        qayta kirishingiz kerak bo‘ladi.
      </p>
      <form id="prov-pwd-modal-form" class="prov-pwd-modal-form" @submit.prevent="submitPassword">
        <p v-if="pwdError" class="prov-inline-error">{{ pwdError }}</p>
        <label class="prov-field">
          <span>Joriy parol</span>
          <input
            v-model="pwd.old_password"
            type="password"
            autocomplete="current-password"
            class="prov-input"
            required
          />
          <span v-if="pwdFieldErrors.old_password" class="prov-field-error">{{
            pwdFieldErrors.old_password
          }}</span>
        </label>
        <label class="prov-field">
          <span>Yangi parol (kamida 8 belgi)</span>
          <input
            v-model="pwd.new_password"
            type="password"
            autocomplete="new-password"
            class="prov-input"
            minlength="8"
            required
          />
          <span v-if="pwdFieldErrors.new_password" class="prov-field-error">{{
            pwdFieldErrors.new_password
          }}</span>
        </label>
        <label class="prov-field">
          <span>Yangi parolni tasdiqlang</span>
          <input
            v-model="pwd.new_password_confirm"
            type="password"
            autocomplete="new-password"
            class="prov-input"
            minlength="8"
            required
          />
          <span v-if="pwdFieldErrors.new_password_confirm" class="prov-field-error">{{
            pwdFieldErrors.new_password_confirm
          }}</span>
        </label>
      </form>
      <template #footer>
        <button type="button" class="btn btn--ghost" :disabled="pwdSubmitting" @click="closePwdModal">
          Bekor
        </button>
        <button
          type="submit"
          form="prov-pwd-modal-form"
          class="btn btn--primary"
          :disabled="pwdSubmitting"
        >
          {{ pwdSubmitting ? 'Saqlanmoqda...' : 'Saqlash' }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.prov-page__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 18px;
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

.prov-account-strip {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px 16px;
  padding: 12px 16px;
  margin-bottom: 18px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  font-size: 13px;
}
.prov-account-strip__label {
  color: #64748b;
}
.prov-account-strip__phone {
  font-weight: 600;
  color: #e5e7eb;
}
.prov-account-strip__name {
  color: #94a3b8;
}

.prov-pwd-cta {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  margin-bottom: 28px;
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.08), rgba(15, 23, 42, 0.9));
  border: 1px solid rgba(249, 115, 22, 0.22);
  border-radius: 14px;
}
.prov-pwd-cta__icon {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 12px;
  background: rgba(249, 115, 22, 0.15);
  color: #fb923c;
}
.prov-pwd-cta__text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.prov-pwd-cta__title {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}
.prov-pwd-cta__desc {
  font-size: 12px;
  color: #94a3b8;
}
.prov-pwd-cta__btn {
  flex-shrink: 0;
  padding: 10px 18px;
  border-radius: 10px;
  border: 1px solid rgba(249, 115, 22, 0.55);
  background: rgba(249, 115, 22, 0.12);
  color: #fdba74;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.15s,
    border-color 0.15s,
    color 0.15s;
}
.prov-pwd-cta__btn:hover {
  background: rgba(249, 115, 22, 0.22);
  border-color: #fb923c;
  color: #fff;
}

.prov-shortcuts__title {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.prov-shortcuts__grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
}
.prov-shortcut-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #0f172a;
  border: 1px solid rgba(255, 255, 255, 0.08);
  text-decoration: none;
  color: inherit;
  transition:
    border-color 0.15s,
    background 0.15s;
}
.prov-shortcut-card:hover {
  border-color: rgba(249, 115, 22, 0.35);
  background: rgba(255, 255, 255, 0.04);
}
.prov-shortcut-card__label {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
}
.prov-shortcut-card__desc {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
}

/* Modal forma */
.prov-modal-lead {
  margin: 0 0 16px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-muted, #64748b);
}
.prov-modal-lead strong {
  color: var(--text, #0f172a);
}
.prov-pwd-modal-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.prov-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.prov-field span:first-child {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}
.prov-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--line, #e2e8f0);
  font-size: 14px;
  background: #fff;
  color: #0f172a;
}
.prov-input:focus {
  outline: none;
  border-color: #f97316;
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.15);
}
.prov-field-error {
  font-size: 12px;
  color: #dc2626;
}
.prov-inline-error {
  margin: 0;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  color: #b91c1c;
  font-size: 13px;
}

@media (max-width: 560px) {
  .prov-pwd-cta {
    flex-wrap: wrap;
  }
  .prov-pwd-cta__btn {
    width: 100%;
  }
}
</style>
