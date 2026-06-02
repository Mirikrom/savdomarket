<script setup>
import { computed, reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import AuthShell from '../../components/AuthShell.vue'
import { useT } from '../../i18n'
import { login } from '../../services/auth.service'
import { resetStoreContextForProvider } from '../../lib/providerStoreAccess'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const isLoading = ref(false)
const apiError = ref('')

const t = useT({
  title: 'auth.login.title',
  subtitle: 'auth.login.subtitle',
  phone: 'auth.login.phone',
  password: 'auth.login.password',
  submit: 'auth.login.submit',
  loading: 'auth.login.loading',
  forgot: 'auth.login.forgot',
  register: 'auth.login.register',
  error: 'auth.login.error',
  passwordChanged: 'auth.login.passwordChanged',
})

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
    try {
      await auth.fetchMe()
    } catch {
      /* ignore */
    }
    if (auth.isSuperuser) {
      resetStoreContextForProvider()
      auth.organizationId = null
      auth.supportMode = false
      router.push('/provider')
    } else {
      router.push({ name: 'pos' })
    }
  } catch (error) {
    apiError.value =
      error?.response?.data?.detail ||
      error?.response?.data?.phone?.[0] ||
      t.error.value
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <AuthShell :title="t.title" :subtitle="t.subtitle">
    <p v-if="passwordChangedHint" class="form-message form-message--success">
      {{ t.passwordChanged }}
    </p>
    <form class="auth-form" @submit.prevent="submit">
      <label class="field">
        <span>{{ t.phone }} <i class="required">*</i></span>
        <input
          v-model.trim="form.phone"
          type="tel"
          autocomplete="tel"
          required
        />
      </label>

      <label class="field">
        <span>{{ t.password }} <i class="required">*</i></span>
        <input
          v-model="form.password"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>

      <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>

      <button class="btn btn--primary" type="submit" :disabled="isLoading">
        {{ isLoading ? t.loading : t.submit }}
      </button>
    </form>

    <footer class="auth-footer">
      <RouterLink to="/auth/forgot-password">{{ t.forgot }}</RouterLink>
      <RouterLink to="/auth/register">{{ t.register }}</RouterLink>
    </footer>
  </AuthShell>
</template>
