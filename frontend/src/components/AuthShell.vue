<script setup>
import AppPreferencesBar from './AppPreferencesBar.vue'
import BrandLogo from './BrandLogo.vue'

defineProps({
  title: {
    type: String,
    required: true,
  },
  subtitle: {
    type: String,
    required: true,
  },
})
</script>

<template>
  <main class="auth-page">
    <AppPreferencesBar floating />
    <section class="auth-showcase">
      <div class="brand brand--logo">
        <BrandLogo variant="auth" />
      </div>
    </section>

    <section class="auth-card">
      <header class="auth-card__header">
        <h2>{{ title }}</h2>
        <p>{{ subtitle }}</p>
      </header>
      <slot />
    </section>
  </main>
</template>
