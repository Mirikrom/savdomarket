<script setup>
import { computed } from 'vue'

/**
 * Yorug' fon (topbar, chek, kassa sidebar): qora logo.
 * Qorong'i fon (admin sidebar, auth, provider): oq logo.
 */
const props = defineProps({
  /** sidebar | sidebar-compact | header | auth | provider | receipt */
  variant: {
    type: String,
    default: 'default',
  },
})

/** Kassa (CashierLayout) sidebar endi yorug‘ — qora logo */
const USE_BLACK_ON_LIGHT_UI = new Set(['header', 'receipt', 'sidebar-compact'])

const src = computed(() => {
  if (USE_BLACK_ON_LIGHT_UI.has(props.variant)) {
    return '/savdopro-logo-black.png'
  }
  return '/savdopro-logo-white.png'
})
</script>

<template>
  <img
    :src="src"
    alt="SavdoPro"
    class="brand-logo"
    :class="variant && variant !== 'default' ? `brand-logo--${variant}` : null"
    loading="lazy"
    decoding="async"
  />
</template>
