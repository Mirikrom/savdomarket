<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

import { checkApiReachable, isOfflineMode, onConnectivityChange } from '../offline/connectivity'

const isOnline = ref(!isOfflineMode())

function refresh() {
  isOnline.value = !isOfflineMode()
}

let unsubscribe = null

async function probe() {
  await checkApiReachable()
  refresh()
}

onMounted(async () => {
  await probe()
  unsubscribe = onConnectivityChange(() => refresh())
  window.addEventListener('online', probe)
  window.addEventListener('offline', probe)
})

onUnmounted(() => {
  unsubscribe?.()
  window.removeEventListener('online', probe)
  window.removeEventListener('offline', probe)
})
</script>

<template>
  <span
    class="connectivity-dot"
    :class="isOnline ? 'connectivity-dot--online' : 'connectivity-dot--offline'"
    role="status"
    :aria-label="isOnline ? 'Server ulangan' : 'Offline — lokal kesh'"
    :title="isOnline ? 'Server ulangan' : 'Offline — lokal kesh'"
  />
</template>

<style scoped>
.connectivity-dot {
  position: absolute;
  top: 0;
  right: 0;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.2);
  flex-shrink: 0;
}

.connectivity-dot--online {
  background: #22c55e;
}

.connectivity-dot--offline {
  background: #ef4444;
}
</style>
