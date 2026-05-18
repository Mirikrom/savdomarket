<script setup>
import { onMounted, reactive, ref } from 'vue'

import AppModal from '../../components/AppModal.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import { categories } from '../../services/catalog.service'

const rows = ref([])
const loading = ref(true)
const modalOpen = ref(false)
const editingId = ref(null)
const apiError = ref('')
const saving = ref(false)

const form = reactive({ name: '' })

const columns = [
  { key: 'name', label: 'Nomi' },
  {
    key: 'created_at',
    label: 'Yaratilgan',
    formatter: (v) => (v ? new Date(v).toLocaleDateString('uz-UZ') : '—'),
    width: '160px',
  },
]

async function fetchData() {
  loading.value = true
  try {
    rows.value = await categories.list()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.name = ''
  apiError.value = ''
  modalOpen.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.name = row.name
  apiError.value = ''
  modalOpen.value = true
}

async function submit() {
  apiError.value = ''
  saving.value = true
  try {
    if (editingId.value) {
      await categories.update(editingId.value, { name: form.name })
    } else {
      await categories.create({ name: form.name })
    }
    modalOpen.value = false
    await fetchData()
  } catch (error) {
    apiError.value =
      error?.response?.data?.detail ||
      error?.response?.data?.name?.[0] ||
      'Saqlashda xatolik.'
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (!confirm(`"${row.name}" kategoriyasi o‘chirilsinmi?`)) return
  try {
    await categories.remove(row.id)
    await fetchData()
  } catch (error) {
    alert(error?.response?.data?.detail || 'O‘chirib bo‘lmadi.')
  }
}

onMounted(fetchData)
</script>

<template>
  <div>
    <PageHeader title="Kategoriyalar" subtitle="Mahsulotlar guruhlanadigan kategoriyalar">
      <template #actions>
        <button class="btn btn--primary" @click="openCreate">+ Yangi kategoriya</button>
      </template>
    </PageHeader>

    <DataTable
      :columns="columns"
      :rows="rows"
      :loading="loading"
      empty-text="Hozircha kategoriyalar yo‘q. Birinchisini yarating."
    >
      <template #actions="{ row }">
        <button class="icon-btn" @click="openEdit(row)">Tahrirlash</button>
        <button class="icon-btn icon-btn--danger" @click="remove(row)">O‘chirish</button>
      </template>
    </DataTable>

    <AppModal
      :open="modalOpen"
      :title="editingId ? 'Kategoriyani tahrirlash' : 'Yangi kategoriya'"
      @close="modalOpen = false"
    >
      <form class="auth-form" @submit.prevent="submit">
        <label class="field">
          <span>Nomi <i class="required">*</i></span>
          <input v-model.trim="form.name" type="text" required maxlength="120" />
        </label>
        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </form>

      <template #footer>
        <button class="btn btn--ghost" type="button" @click="modalOpen = false">Bekor qilish</button>
        <button class="btn btn--primary" :disabled="saving" @click="submit">
          {{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
        </button>
      </template>
    </AppModal>
  </div>
</template>
