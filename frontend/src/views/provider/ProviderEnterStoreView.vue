<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import providerService from '../../services/provider.service'
import { enterClientStore } from '../../lib/providerStoreAccess'
import { useAuthStore } from '../../stores/auth'
import { useOrganizationStore } from '../../stores/organization'

const router = useRouter()
const auth = useAuthStore()
const org = useOrganizationStore()

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const search = ref('')
const organizations = ref([])

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return organizations.value
  return organizations.value.filter(
    (o) =>
      o.name?.toLowerCase().includes(q) ||
      String(o.id).includes(q) ||
      o.owner_phone?.toLowerCase?.().includes(q),
  )
})

onMounted(async () => {
  if (!auth.isSuperuser) {
    router.replace('/app')
    return
  }
  try {
    organizations.value = await providerService.orgs.list()
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Mijozlar ro‘yxati yuklanmadi.'
  } finally {
    loading.value = false
  }
})

async function pick(orgRow) {
  if (!orgRow?.is_active) {
    error.value = 'To‘xtatilgan mijoz do‘koniga kirish mumkin emas.'
    return
  }
  error.value = ''
  saving.value = true
  try {
    await enterClientStore(router, auth, org, orgRow)
  } catch (e) {
    error.value =
      e?.response?.data?.detail ||
      e?.message ||
      'Do‘konga kirishda xatolik. Owner mavjudligini tekshiring.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="prov-enter">
    <h1 class="prov-enter__title">Qaysi mijoz do‘koniga kirmoqchisiz?</h1>
    <p class="prov-enter__sub">
      Tanlangan do‘konda siz <strong>egasi (owner)</strong> huquqlari bilan ishlaysiz. Super Admin
      panelga istalgan vaqt qaytishingiz mumkin.
    </p>

    <input
      v-model="search"
      type="search"
      class="prov-enter__search"
      placeholder="Nom, ID yoki telefon bo‘yicha qidirish..."
      :disabled="loading || saving"
    />

    <p v-if="error" class="prov-enter__error">{{ error }}</p>

    <div v-if="loading" class="prov-enter__loading">Yuklanmoqda...</div>
    <ul v-else class="prov-enter__list">
      <li v-for="orgRow in filtered" :key="orgRow.id">
        <button
          type="button"
          class="prov-enter__row"
          :disabled="saving || !orgRow.is_active"
          @click="pick(orgRow)"
        >
          <span class="prov-enter__name">{{ orgRow.name }}</span>
          <span class="prov-enter__meta">ID {{ orgRow.id }}</span>
          <span v-if="!orgRow.is_active" class="prov-enter__badge">To‘xtatilgan</span>
        </button>
      </li>
      <li v-if="!filtered.length" class="prov-enter__empty">Mijoz topilmadi.</li>
    </ul>

    <button type="button" class="prov-enter__back" @click="router.push({ name: 'provider-dashboard' })">
      ← Provider panelga
    </button>
  </div>
</template>

<style scoped>
.prov-enter {
  max-width: 560px;
  margin: 0 auto;
}

.prov-enter__title {
  margin: 0 0 8px;
  font-size: 1.35rem;
  color: #fff;
}

.prov-enter__sub {
  margin: 0 0 20px;
  color: #94a3b8;
  font-size: 0.95rem;
  line-height: 1.45;
}

.prov-enter__search {
  width: 100%;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: #1e293b;
  color: #fff;
  margin-bottom: 16px;
}

.prov-enter__error {
  color: #fca5a5;
  margin-bottom: 12px;
}

.prov-enter__loading,
.prov-enter__empty {
  color: #94a3b8;
  padding: 24px 0;
}

.prov-enter__list {
  list-style: none;
  margin: 0 0 20px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prov-enter__row {
  width: 100%;
  text-align: left;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: #1e293b;
  color: #e5e7eb;
  cursor: pointer;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}

.prov-enter__row:hover:not(:disabled) {
  border-color: rgba(249, 115, 22, 0.45);
  background: #243044;
}

.prov-enter__row:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.prov-enter__name {
  font-weight: 600;
  flex: 1;
}

.prov-enter__meta {
  font-size: 0.85rem;
  color: #94a3b8;
}

.prov-enter__badge {
  font-size: 0.75rem;
  color: #fca5a5;
}

.prov-enter__back {
  background: transparent;
  border: 0;
  color: #94a3b8;
  cursor: pointer;
  font-size: 0.95rem;
}

.prov-enter__back:hover {
  color: #fff;
}
</style>
