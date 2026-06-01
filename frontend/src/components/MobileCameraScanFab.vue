<script setup>
import { useIsMobileViewport } from '../composables/useIsMobileViewport'
import { useI18n } from '../i18n'

const props = defineProps({
  /** i18n kaliti (masalan `pos.scanCamera`). */
  labelKey: { type: String, required: true },
})

defineEmits(['click'])

const { tr } = useI18n()
const { isMobile } = useIsMobileViewport()
</script>

<template>
  <button
    v-if="isMobile"
    type="button"
    class="mobile-camera-scan-fab"
    :aria-label="tr(labelKey)"
    @click="$emit('click')"
  >
    <span class="mobile-camera-scan-fab__icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2">
        <path
          d="M5 7h2l1-2h8l1 2h2a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9a2 2 0 012-2z"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <circle cx="12" cy="13" r="3.5" />
        <path d="M4 4h2M20 4h-2" stroke-linecap="round" opacity="0.5" />
      </svg>
    </span>
    <span class="mobile-camera-scan-fab__label">{{ tr(labelKey) }}</span>
  </button>
</template>
