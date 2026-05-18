<script setup>
import { computed, onUnmounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import AuthShell from '../../components/AuthShell.vue'
import {
  registerComplete,
  registerRequestOtp,
  registerVerifyOtp,
} from '../../services/auth.service'

const router = useRouter()
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
  <AuthShell
    title="Ro‘yxatdan o‘tish"
    subtitle="Telefon raqamingizni tasdiqlab, hisob oching"
  >
    <ol class="stepper">
      <li :class="{ 'is-active': step >= 1, 'is-done': step > 1 }">Telefon</li>
      <li :class="{ 'is-active': step >= 2, 'is-done': step > 2 }">Kod</li>
      <li :class="{ 'is-active': step >= 3 }">Profil</li>
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
        <strong>{{ maskedPhone }}</strong> raqamga 6 xonali kod yubordik.
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

    <form v-else class="auth-form auth-form--grid" @submit.prevent="submitProfile">
      <label class="field field--full">
        <span>To‘liq ism <i class="required">*</i></span>
        <input v-model.trim="profileForm.full_name" type="text" required />
      </label>

      <label class="field field--full">
        <span>Magazin nomi</span>
        <input
          v-model.trim="profileForm.organization_name"
          type="text"
          placeholder="Masalan: Ali Market"
        />
      </label>

      <label class="field field--full">
        <span>Email (ixtiyoriy)</span>
        <input v-model.trim="profileForm.email" type="email" />
      </label>

      <label class="field">
        <span>Til</span>
        <select v-model="profileForm.preferred_language">
          <option value="uz">O‘zbekcha</option>
          <option value="ru">Русский</option>
          <option value="en">English</option>
        </select>
      </label>

      <label class="field">
        <span>Parol <i class="required">*</i></span>
        <input v-model="profileForm.password" type="password" minlength="8" required />
      </label>

      <label class="field field--full">
        <span>Parolni tasdiqlang <i class="required">*</i></span>
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
        {{ isLoading ? 'Yaratilmoqda...' : 'Hisobni yaratish' }}
      </button>
    </form>

    <footer class="auth-footer">
      <RouterLink to="/auth/login">Akkauntingiz bormi? Kirish</RouterLink>
    </footer>
  </AuthShell>
</template>
