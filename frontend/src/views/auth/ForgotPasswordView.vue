<script setup>
import { computed, onUnmounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { RouterLink, useRouter } from 'vue-router'

import AuthShell from '../../components/AuthShell.vue'
import { translate, useT, useTParam } from '../../i18n'
import {
  forgotPasswordRequest,
  forgotPasswordVerify,
  resetPassword,
} from '../../services/auth.service'
import { useUiStore } from '../../stores/ui'

const router = useRouter()
const ui = useUiStore()
const { locale } = storeToRefs(ui)
const step = ref(1)
const isLoading = ref(false)
const apiError = ref('')
const successMessage = ref('')

const t = useT({
  title: 'auth.forgot.title',
  subtitle: 'auth.forgot.subtitle',
  phone: 'auth.login.phone',
  getCode: 'auth.register.getCode',
  sending: 'auth.register.sending',
  otpLabel: 'auth.register.otpLabel',
  continue: 'auth.register.continue',
  checking: 'auth.register.checking',
  resend: 'auth.register.resend',
  changePhone: 'auth.register.changePhone',
  newPassword: 'auth.forgot.newPassword',
  confirmPassword: 'auth.forgot.confirmPassword',
  save: 'auth.forgot.save',
  saving: 'auth.forgot.saving',
  backLogin: 'auth.forgot.backLogin',
})

const phoneForm = reactive({ phone: '' })
const otpForm = reactive({ code: '' })
const passwordForm = reactive({ new_password: '', new_password_confirm: '' })

const resetToken = ref('')
const maskedPhone = ref('')
const secondsLeft = ref(0)
let countdownTimer = null

const otpHint = useTParam('auth.forgot.otpHint', () => ({ phone: maskedPhone.value }))

const resendLabel = computed(() => {
  if (canResend.value) return t.resend.value
  return translate(locale.value, 'auth.register.resendWait', { s: secondsLeft.value })
})

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
    const response = await forgotPasswordRequest(phoneForm.phone)
    maskedPhone.value = response.phone || phoneForm.phone
    startCountdown(120)
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
    const response = await forgotPasswordVerify({
      phone: phoneForm.phone,
      code: otpForm.code,
    })
    resetToken.value = response.reset_token
    step.value = 3
  } catch (error) {
    apiError.value = extractError(error, 'Kod noto‘g‘ri yoki muddati tugagan.')
  } finally {
    isLoading.value = false
  }
}

async function submitPassword() {
  apiError.value = ''
  successMessage.value = ''
  if (passwordForm.new_password !== passwordForm.new_password_confirm) {
    apiError.value = 'Parollar mos kelmadi.'
    return
  }
  isLoading.value = true
  try {
    await resetPassword({
      reset_token: resetToken.value,
      new_password: passwordForm.new_password,
    })
    successMessage.value = 'Parol yangilandi. Endi yangi parol bilan kiring.'
    setTimeout(() => router.push('/auth/login'), 900)
  } catch (error) {
    apiError.value = extractError(error, 'Parolni yangilashda xatolik.')
  } finally {
    isLoading.value = false
  }
}

async function resendOtp() {
  if (!canResend.value || isLoading.value) return
  apiError.value = ''
  isLoading.value = true
  try {
    await forgotPasswordRequest(phoneForm.phone)
    startCountdown(120)
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

    <form v-else class="auth-form" @submit.prevent="submitPassword">
      <label class="field">
        <span>{{ t.newPassword }} <i class="required">*</i></span>
        <input
          v-model="passwordForm.new_password"
          type="password"
          autocomplete="new-password"
          minlength="8"
          required
        />
      </label>

      <label class="field">
        <span>{{ t.confirmPassword }} <i class="required">*</i></span>
        <input
          v-model="passwordForm.new_password_confirm"
          type="password"
          autocomplete="new-password"
          minlength="8"
          required
        />
      </label>

      <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      <p v-if="successMessage" class="form-message form-message--success">{{ successMessage }}</p>

      <button class="btn btn--primary" type="submit" :disabled="isLoading">
        {{ isLoading ? t.saving : t.save }}
      </button>
    </form>

    <footer class="auth-footer">
      <RouterLink to="/auth/login">{{ t.backLogin }}</RouterLink>
    </footer>
  </AuthShell>
</template>
