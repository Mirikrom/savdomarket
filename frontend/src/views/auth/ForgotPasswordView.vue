<script setup>
import { computed, onUnmounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import AuthShell from '../../components/AuthShell.vue'
import {
  forgotPasswordRequest,
  forgotPasswordVerify,
  resetPassword,
} from '../../services/auth.service'

const router = useRouter()
const step = ref(1)
const isLoading = ref(false)
const apiError = ref('')
const successMessage = ref('')

const phoneForm = reactive({ phone: '' })
const otpForm = reactive({ code: '' })
const passwordForm = reactive({ new_password: '', new_password_confirm: '' })

const resetToken = ref('')
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
  <AuthShell title="Parolni tiklash" subtitle="Telefon orqali tasdiqlab, yangi parol o‘rnating">
    <ol class="stepper">
      <li :class="{ 'is-active': step >= 1, 'is-done': step > 1 }">Telefon</li>
      <li :class="{ 'is-active': step >= 2, 'is-done': step > 2 }">Kod</li>
      <li :class="{ 'is-active': step >= 3 }">Yangi parol</li>
    </ol>

    <form v-if="step === 1" class="auth-form" @submit.prevent="submitPhone">
      <label class="field">
        <span>Telefon raqam <i class="required">*</i></span>
        <input
          v-model.trim="phoneForm.phone"
          type="tel"
          autocomplete="tel"
          placeholder="+998 90 123 45 67"
          required
        />
      </label>

      <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>

      <button class="btn btn--primary" type="submit" :disabled="isLoading">
        {{ isLoading ? 'Yuborilmoqda...' : 'Kod olish' }}
      </button>
    </form>

    <form v-else-if="step === 2" class="auth-form" @submit.prevent="submitOtp">
      <p class="form-hint">
        Agar raqam bazada bo‘lsa, <strong>{{ maskedPhone }}</strong> ga kod yubordik.
      </p>

      <label class="field">
        <span>Tasdiqlash kodi <i class="required">*</i></span>
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
        {{ isLoading ? 'Tekshirilmoqda...' : 'Davom etish' }}
      </button>

      <div class="resend">
        <button type="button" class="link-btn" :disabled="!canResend" @click="resendOtp">
          {{ canResend ? 'Kodni qayta yuborish' : `Qayta yuborish ${secondsLeft}s` }}
        </button>
        <button type="button" class="link-btn" @click="backToPhone">Raqamni o‘zgartirish</button>
      </div>
    </form>

    <form v-else class="auth-form" @submit.prevent="submitPassword">
      <label class="field">
        <span>Yangi parol <i class="required">*</i></span>
        <input
          v-model="passwordForm.new_password"
          type="password"
          autocomplete="new-password"
          minlength="8"
          required
        />
      </label>

      <label class="field">
        <span>Parolni tasdiqlang <i class="required">*</i></span>
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
        {{ isLoading ? 'Saqlanmoqda...' : 'Parolni yangilash' }}
      </button>
    </form>

    <footer class="auth-footer">
      <RouterLink to="/auth/login">Kirish sahifasiga qaytish</RouterLink>
    </footer>
  </AuthShell>
</template>
