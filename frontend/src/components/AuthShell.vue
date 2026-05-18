<script setup>
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
    <section class="auth-showcase">
      <div class="brand brand--logo">
        <BrandLogo variant="auth" />
      </div>
      <p class="showcase__text">
        Do'konlar uchun tezkor, ishonchli va kengayadigan savdo tizimi.
      </p>
      <ul class="showcase__list">
        <li>Kassa va ombor bir tizimda</li>
        <li>Role va permission boshqaruvi</li>
        <li>Lite va Pro paketlar</li>
      </ul>
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
