<script setup>
defineProps({
  /** synced | pending | canceled | returned */
  kind: {
    type: String,
    required: true,
  },
  label: {
    type: String,
    default: '',
  },
})
</script>

<template>
  <span
    class="sync-status-icon"
    :class="`sync-status-icon--${kind}`"
    :title="label"
    :aria-label="label || kind"
  >
    <svg
      v-if="kind === 'synced'"
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.15" />
      <path
        d="M8 12.5l2.5 2.5L16 9"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    <svg
      v-else-if="kind === 'canceled'"
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.12" />
      <path
        d="M9 9l6 6M15 9l-6 6"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
      />
    </svg>
    <svg
      v-else-if="kind === 'returned'"
      viewBox="0 0 24 24"
      width="22"
      height="22"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M9 8H5v4M5 12c1.5 2.8 4.2 4.5 7.5 4.5 4.1 0 7.5-3.4 7.5-7.5S16.6 1.5 12.5 1.5 5 4.9 5 9"
        stroke="currentColor"
        stroke-width="1.75"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
    <svg
      v-else
      class="sync-status-icon__pending-svg"
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.25" opacity="0.22" />
      <path
        d="M4 12a8 8 0 0 1 13.2-5.8M20 5.5V10h-4.5M20 12a8 8 0 0 1-13.2 5.8M4 18.5V14H8.5"
        stroke="currentColor"
        stroke-width="1.85"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  </span>
</template>

<style scoped>
.sync-status-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: default;
}

.sync-status-icon--synced {
  color: #16a34a;
  background: #dcfce7;
}

.sync-status-icon--pending {
  color: #d97706;
  background: linear-gradient(145deg, #fffbeb 0%, #fef3c7 100%);
  box-shadow: inset 0 0 0 1px rgba(217, 119, 6, 0.12);
}

.sync-status-icon__pending-svg {
  animation: sync-status-spin 1.4s linear infinite;
}

.sync-status-icon--canceled {
  color: #b91c1c;
  background: #fee2e2;
}

.sync-status-icon--returned {
  color: #b45309;
  background: #fef3c7;
}

@keyframes sync-status-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
