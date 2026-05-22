<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { storeToRefs } from 'pinia'

import AppModal from '../../components/AppModal.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import { numberLocaleForUi, useI18n } from '../../i18n'
import { useApiNotify } from '../../composables/useApiNotify'
import { categories } from '../../services/catalog.service'
import { useUiStore } from '../../stores/ui'

const { tr } = useI18n()
const { showApiError } = useApiNotify()
const { locale } = storeToRefs(useUiStore())

const rows = ref([])
const loading = ref(true)
const modalOpen = ref(false)
const editingId = ref(null)
const apiError = ref('')
const saving = ref(false)

const form = reactive({ name: '' })

const dateLocale = computed(() => numberLocaleForUi(locale.value))

const columns = computed(() => [
  { key: 'name', label: tr('table.column.name') },
  {
    key: 'created_at',
    label: tr('table.column.created'),
    formatter: (v) => (v ? new Date(v).toLocaleDateString(dateLocale.value) : '—'),
    width: '160px',
  },
])

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
      tr('page.categories.saveError')
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (!confirm(tr('page.categories.deleteConfirm', { name: row.name }))) return
  try {
    await categories.remove(row.id)
    await fetchData()
  } catch (error) {
    showApiError(error, 'page.categories.deleteFail')
  }
}

onMounted(fetchData)
</script>

<template>
  <div>
    <PageHeader :title="tr('page.categories.title')" :subtitle="tr('page.categories.subtitle')">
      <template #actions>
        <button class="btn btn--primary" @click="openCreate">{{ tr('page.categories.addBtn') }}</button>
      </template>
    </PageHeader>

    <DataTable
      :columns="columns"
      :rows="rows"
      :loading="loading"
      :empty-text="tr('page.categories.emptyTable')"
    >
      <template #actions="{ row }">
        <button class="icon-btn" @click="openEdit(row)">{{ tr('page.categories.edit') }}</button>
        <button class="icon-btn icon-btn--danger" @click="remove(row)">{{ tr('page.categories.delete') }}</button>
      </template>
    </DataTable>

    <AppModal
      :open="modalOpen"
      :title="editingId ? tr('page.categories.modalEdit') : tr('page.categories.modalNew')"
      @close="modalOpen = false"
    >
      <form class="auth-form" @submit.prevent="submit">
        <label class="field">
          <span>{{ tr('page.categories.fieldNameLabel') }} <i class="required">*</i></span>
          <input v-model.trim="form.name" type="text" required maxlength="120" />
        </label>
        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </form>

      <template #footer>
        <button class="btn btn--ghost" type="button" @click="modalOpen = false">
          {{ tr('page.categories.cancel') }}
        </button>
        <button class="btn btn--primary" :disabled="saving" @click="submit">
          {{ saving ? tr('page.categories.saving') : tr('page.categories.save') }}
        </button>
      </template>
    </AppModal>
  </div>
</template>
