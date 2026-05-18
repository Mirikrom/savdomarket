<script setup>
import { onMounted, reactive, ref } from 'vue'

import AppModal from '../../components/AppModal.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import { branches } from '../../services/shops.service'
import { useOrganizationStore } from '../../stores/organization'

const org = useOrganizationStore()

const rows = ref([])
const loading = ref(true)
const modalOpen = ref(false)
const editingId = ref(null)
const saving = ref(false)
const apiError = ref('')

const form = reactive({ name: '', address: '', is_main: false })

const columns = [
  { key: 'name', label: 'Filial nomi' },
  { key: 'address', label: 'Manzil' },
  {
    key: 'is_main',
    label: 'Asosiy',
    formatter: (v) => (v ? '✓' : ''),
    width: '80px',
  },
]

async function fetchData() {
  loading.value = true
  try {
    rows.value = await branches.list()
    await org.fetchBranches()
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.address = ''
  form.is_main = false
  apiError.value = ''
  modalOpen.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.name = row.name
  form.address = row.address || ''
  form.is_main = row.is_main
  apiError.value = ''
  modalOpen.value = true
}

async function submit() {
  apiError.value = ''
  saving.value = true
  try {
    if (editingId.value) await branches.update(editingId.value, { ...form })
    else await branches.create({ ...form })
    modalOpen.value = false
    await fetchData()
  } catch (error) {
    apiError.value =
      error?.response?.data?.detail ||
      Object.values(error?.response?.data || {})?.[0]?.[0] ||
      'Saqlashda xatolik.'
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (!confirm(`"${row.name}" filiali o‘chirilsinmi?`)) return
  try {
    await branches.remove(row.id)
    await fetchData()
  } catch (error) {
    alert(error?.response?.data?.detail || 'O‘chirib bo‘lmadi.')
  }
}

onMounted(fetchData)
</script>

<template>
  <div>
    <PageHeader title="Filiallar" subtitle="Tashkilotning filiallari va manzillari">
      <template #actions>
        <button class="btn btn--primary" @click="openCreate">+ Yangi filial</button>
      </template>
    </PageHeader>

    <DataTable
      :columns="columns"
      :rows="rows"
      :loading="loading"
      empty-text="Hozircha filiallar yo‘q."
    >
      <template #actions="{ row }">
        <button class="icon-btn" @click="openEdit(row)">Tahrirlash</button>
        <button class="icon-btn icon-btn--danger" @click="remove(row)">O‘chirish</button>
      </template>
    </DataTable>

    <AppModal
      :open="modalOpen"
      :title="editingId ? 'Filialni tahrirlash' : 'Yangi filial'"
      @close="modalOpen = false"
    >
      <form class="auth-form" @submit.prevent="submit">
        <label class="field">
          <span>Filial nomi <i class="required">*</i></span>
          <input v-model.trim="form.name" type="text" required maxlength="255" />
        </label>
        <label class="field">
          <span>Manzil</span>
          <input v-model.trim="form.address" type="text" maxlength="255" />
        </label>
        <label class="field" style="flex-direction: row; align-items: center; gap: 10px">
          <input v-model="form.is_main" type="checkbox" style="width: auto" />
          <span style="text-transform: none">Asosiy filial sifatida belgilash</span>
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
