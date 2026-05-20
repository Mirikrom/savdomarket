<script setup>
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink, useRouter } from 'vue-router'

import AuthShell from '../../components/AuthShell.vue'
import { translate, useT, useTParam } from '../../i18n'
import {
  registerComplete,
  registerRequestOtp,
  registerVerifyOtp,
} from '../../services/auth.service'
import { useUiStore } from '../../stores/ui'

const router = useRouter()
const ui = useUiStore()
const { locale } = storeToRefs(ui)

const t = useT({
  title: 'auth.register.title',
  subtitle: 'auth.register.subtitle',
  phone: 'auth.login.phone',
  getCode: 'auth.register.getCode',
  sending: 'auth.register.sending',
  otpLabel: 'auth.register.otpLabel',
  continue: 'auth.register.continue',
  checking: 'auth.register.checking',
  resend: 'auth.register.resend',
  changePhone: 'auth.register.changePhone',
  fullName: 'auth.register.fullName',
  shopName: 'auth.register.shopName',
  email: 'auth.register.email',
  password: 'auth.register.password',
  passwordConfirm: 'auth.register.passwordConfirm',
  create: 'auth.register.create',
  creating: 'auth.register.creating',
  hasAccount: 'auth.register.hasAccount',
})
const step = ref(1)
const isLoading = ref(false)
const apiError = ref('')
const successMessage = ref('')

const phoneForm = reactive({ phone: '' })
const otpForm = reactive({ code: '' })
const profileForm = reactive({
  full_name: '',
  organization_name: '',
  email: '',
  password: '',
  password_confirm: '',
  preferred_language: 'uz',
})

const registrationToken = ref('')
const maskedPhone = ref('')
const secondsLeft = ref(0)
let countdownTimer = null

function startCountdown(seconds) {
  secondsLeft.value = seconds
  clearInterval(countdownTimer)
  countdownTimer = setInterval(() => {
    if (secondsLeft.value > 0) secondsLeft.value -= 1
    else clearInterval(countdownTimer)
  }, 1000)
}

onUnmounted(() => clearInterval(countdownTimer))

const canResend = computed(() => secondsLeft.value === 0)

const otpHint = useTParam('auth.register.otpHint', () => ({ phone: maskedPhone.value }))

const resendLabel = computed(() => {
  if (canResend.value) return t.resend.value
  return translate(locale.value, 'auth.register.resendWait', { s: secondsLeft.value })
})

watch(
  locale,
  (lang) => {
    profileForm.preferred_language = lang
  },
  { immediate: true },
)

function extractError(error, fallback) {
  const data = error?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  for (const value of Object.values(data)) {
    if (Array.isArray(value) && value[0]) return value[0]
    if (typeof value === 'string') return value
  }
  return fallback
}

async function submitPhone() {
  apiError.value = ''
  isLoading.value = true
  try {
    const response = await registerRequestOtp(phoneForm.phone)
    maskedPhone.value = response.phone || phoneForm.phone
    startCountdown(response.expires_in || 120)
    otpForm.code = ''
    step.value = 2
  } catch (error) {
    apiError.value = extractError(error, 'Kod yuborishda xatolik.')
  } finally {
    isLoading.value = false
  }
}

async function submitOtp() {
  apiError.value = ''
  isLoading.value = true
  try {
    const response = await registerVerifyOtp({
      phone: phoneForm.phone,
      code: otpForm.code,
    })
    registrationToken.value = response.registration_token
    step.value = 3
  } catch (error) {
    apiError.value = extractError(error, 'Kod noto‘g‘ri yoki muddati tugagan.')
  } finally {
    isLoading.value = false
  }
}

async function submitProfile() {
  apiError.value = ''
  successMessage.value = ''
  if (profileForm.password !== profileForm.password_confirm) {
    apiError.value = 'Parollar mos kelmadi.'
    return
  }
  isLoading.value = true
  try {
    await registerComplete({
      registration_token: registrationToken.value,
      full_name: profileForm.full_name,
      email: profileForm.email,
      password: profileForm.password,
      password_confirm: profileForm.password_confirm,
      organization_name: profileForm.organization_name,
      preferred_language: profileForm.preferred_language,
    })
    successMessage.value = 'Ro‘yxatdan o‘tish muvaffaqiyatli yakunlandi.'
    setTimeout(() => router.push('/app'), 700)
  } catch (error) {
    apiError.value = extractError(error, 'Ro‘yxatdan o‘tishda xatolik.')
  } finally {
    isLoading.value = false
  }
}

async function resendOtp() {
  if (!canResend.value || isLoading.value) return
  apiError.value = ''
  isLoading.value = true
  try {
    const response = await registerRequestOtp(phoneForm.phone)
    startCountdown(response.expires_in || 120)
    otpForm.code = ''
  } catch (error) {
    apiError.value = extractError(error, 'Kod qayta yuborilmadi.')
  } finally {
    isLoading.value = false
  }
}

function backToPhone() {
  step.value = 1
  apiError.value = ''
  clearInterval(countdownTimer)
  secondsLeft.value = 0
}
</script>

<template>
  <AuthShell :title="t.title" :subtitle="t.subtitle">
    <form v-if="step === 1" class="auth-form" @submit.prevent="submitPhone">
      <label class="field">
        <span>{{ t.phone }} <i class="required">*</i></span>
        <input
          v-model.trim="phoneForm.phone"
          type="tel"
          autocomplete="tel"
          required
        />
      </label>

      <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>

      <button class="btn btn--primary" type="submit" :disabled="isLoading">
        {{ isLoading ? t.sending : t.getCode }}
      </button>
    </form>

    <form v-else-if="step === 2" class="auth-form" @submit.prevent="submitOtp">
      <p class="form-hint">{{ otpHint }}</p>

      <label class="field">
        <span>{{ t.otpLabel }} <i class="required">*</i></span>
        <input
          v-model.trim="otpForm.code"
          class="otp-input"
          type="text"
          inputmode="numeric"
          pattern="[0-9]*"
          autocomplete="one-time-code"
          maxlength="6"
          required
        />
      </label>

      <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>

      <button class="btn btn--primary" type="submit" :disabled="isLoading">
        {{ isLoading ? t.checking : t.continue }}
      </button>

      <div class="resend">
        <button type="button" class="link-btn" :disabled="!canResend" @click="resendOtp">
          {{ resendLabel }}
        </button>
        <button type="button" class="link-btn" @click="backToPhone">{{ t.changePhone }}</button>
      </div>
    </form>

    <form v-else class="auth-form auth-form--grid" @submit.prevent="submitProfile">
      <label class="field field--full">
        <span>{{ t.fullName }} <i class="required">*</i></span>
        <input v-model.trim="profileForm.full_name" type="text" required />
      </label>

      <label class="field field--full">
        <span>{{ t.shopName }}</span>
        <input v-model.trim="profileForm.organization_name" type="text" />
      </label>

      <label class="field field--full">
        <span>{{ t.email }}</span>
        <input v-model.trim="profileForm.email" type="email" />
      </label>

      <label class="field field--full">
        <span>{{ t.password }} <i class="required">*</i></span>
        <input v-model="profileForm.password" type="password" minlength="8" required />
      </label>

      <label class="field field--full">
        <span>{{ t.passwordConfirm }} <i class="required">*</i></span>
        <input
          v-model="profileForm.password_confirm"
          type="password"
          minlength="8"
          required
        />
      </label>

      <p v-if="apiError" class="form-message form-message--error field--full">
        {{ apiError }}
      </p>
      <p v-if="successMessage" class="form-message form-message--success field--full">
        {{ successMessage }}
      </p>

      <button class="btn btn--primary field--full" type="submit" :disabled="isLoading">
        {{ isLoading ? t.creating : t.create }}
      </button>
    </form>

    <footer class="auth-footer">
      <RouterLink to="/auth/login">{{ t.hasAccount }}</RouterLink>
    </footer>
  </AuthShell>
</template>
