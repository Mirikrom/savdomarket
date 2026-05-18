<script setup>
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import AuthShell from '../../components/AuthShell.vue'
import { login } from '../../services/auth.service'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const isLoading = ref(false)
const apiError = ref('')

const passwordChangedHint = computed(
  () => route.query.password_changed === '1',
)
const form = reactive({
  phone: '',
  password: '',
})

async function submit() {
  apiError.value = ''
  isLoading.value = true
  try {
    await login(form)
    // /me/ chaqirib, foydalanuvchi turini aniqlaymiz: provider bo'lsa
    // alohida panelga, oddiy bo'lsa /app'ga.
    try {
      await auth.fetchMe()
    } catch {
      /* ignore — /app ga o'tib o'zi qayta yuklaydi */
    }
    if (auth.isSuperuser) {
      router.push('/provider')
    } else {
      router.push({ name: 'pos' })
    }
  } catch (error) {
    apiError.value =
      error?.response?.data?.detail ||
      error?.response?.data?.phone?.[0] ||
      'Telefon yoki parol noto‘g‘ri.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <AuthShell title="Tizimga kirish" subtitle="Telefon raqam va parol orqali kiring">
    <p v-if="passwordChangedHint" class="form-message form-message--success">
      Parol muvaffaqiyatli yangilandi. Yangi parol bilan qayta kiring.
    </p>
    <form class="auth-form" @submit.prevent="submit">
      <label class="field">
        <span>Telefon raqam <i class="required">*</i></span>
        <input
          v-model.trim="form.phone"
          type="tel"
          autocomplete="tel"
          placeholder="+998 90 123 45 67"
          required
        />
      </label>

      <label class="field">
        <span>Parol <i class="required">*</i></span>
        <input
          v-model="form.password"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>

      <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>

      <button class="btn btn--primary" type="submit" :disabled="isLoading">
        {{ isLoading ? 'Kirilmoqda...' : 'Kirish' }}
      </button>
    </form>

    <footer class="auth-footer">
      <RouterLink to="/auth/forgot-password">Parolni unutdingizmi?</RouterLink>
      <RouterLink to="/auth/register">Ro‘yxatdan o‘tish</RouterLink>
    </footer>
  </AuthShell>
</template>
