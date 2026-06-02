<script setup>
import { useRouter } from 'vue-router'

import { exitToProviderPanel } from '../lib/providerStoreAccess'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

function goProvider() {
  exitToProviderPanel(router, auth)
}
</script>

<template>
  <div v-if="auth.supportMode" class="support-banner" role="status">
    <span class="support-banner__text">
      Qo‘llab-quvvatlash rejimi:
      <strong>{{ auth.organizationName || `#${auth.organizationId}` }}</strong>
      (owner huquqlari)
    </span>
    <button type="button" class="support-banner__btn" @click="goProvider">
      Super Admin panel
    </button>
  </div>
</template>

<style scoped>
.support-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 16px;
  background: linear-gradient(90deg, #fff7ed, #ffedd5);
  border-bottom: 1px solid #fdba74;
  color: #9a3412;
  font-size: 0.9rem;
}

.support-banner__btn {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #fb923c;
  background: #fff;
  color: #c2410c;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.85rem;
}

.support-banner__btn:hover {
  background: #fff7ed;
}
</style>
