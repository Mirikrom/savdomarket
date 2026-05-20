<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import PageHeader from '../../components/PageHeader.vue'
import { useI18n } from '../../i18n'
import { products as productsApi } from '../../services/catalog.service'
import { stockMovements } from '../../services/inventory.service'
import { useOrganizationStore } from '../../stores/organization'

const router = useRouter()
const org = useOrganizationStore()
const { tr } = useI18n()

const productList = ref([])
const loading = ref(true)
const saving = ref(false)
const apiError = ref('')
const successMsg = ref('')

const REASONS = [
  { value: 'out', label: 'Chiqim (yo‘qotish, buzilgan)' },
  { value: 'adjust', label: 'Inventarizatsiya tuzatish (sanab ko‘rish)' },
  { value: 'return', label: 'Qaytarish (mijozdan qaytdi)' },
]

const form = reactive({
  branch: '',
  product: '',
  movement_type: 'out',
  quantity: '1',
  note: '',
})

const selectedProduct = computed(() =>
  productList.value.find((p) => p.id === Number(form.product)),
)

async function fetchProducts() {
  loading.value = true
  try {
    productList.value = await productsApi.list()
  } finally {
    loading.value = false
  }
}

async function submit() {
  apiError.value = ''
  successMsg.value = ''

  if (!form.branch) {
    apiError.value = 'Filialni tanlang.'
    return
  }
  if (!form.product) {
    apiError.value = 'Mahsulotni tanlang.'
    return
  }
  if (!Number(form.quantity)) {
    apiError.value = 'Miqdor 0 dan farqli bo‘lishi shart.'
    return
  }

  saving.value = true
  try {
    const payload = {
      branch: Number(form.branch),
      product: Number(form.product),
      movement_type: form.movement_type,
      quantity: form.quantity,
      note: form.note,
    }
    await stockMovements.create(payload)
    successMsg.value = 'Ombor harakati saqlandi.'
    form.product = ''
    form.quantity = '1'
    form.note = ''
  } catch (error) {
    const data = error?.response?.data
    apiError.value =
      data?.detail ||
      (typeof data === 'object' ? JSON.stringify(data) : '') ||
      'Saqlashda xatolik.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await fetchProducts()
  if (org.currentBranchId) form.branch = String(org.currentBranchId)
})
</script>

<template>
  <div>
    <PageHeader
      :title="tr('page.adjust.title')"
      :subtitle="tr('page.adjust.subtitle')"
    >
      <template #actions>
        <button class="btn btn--ghost" @click="router.push('/app/inventory')">
          {{ tr('page.adjust.backToStock') }}
        </button>
      </template>
    </PageHeader>

    <form class="card adj-form" @submit.prevent="submit">
      <label class="field">
        <span>Filial <i class="required">*</i></span>
        <select v-model="form.branch" required>
          <option value="" disabled>— Filial tanlang —</option>
          <option v-for="b in org.branches" :key="b.id" :value="b.id">{{ b.name }}</option>
        </select>
      </label>

      <label class="field">
        <span>Sabab <i class="required">*</i></span>
        <select v-model="form.movement_type" required>
          <option v-for="r in REASONS" :key="r.value" :value="r.value">{{ r.label }}</option>
        </select>
      </label>

      <label class="field field--full">
        <span>Mahsulot <i class="required">*</i></span>
        <select v-model="form.product" :disabled="loading" required>
          <option value="" disabled>— Tanlang —</option>
          <option v-for="p in productList" :key="p.id" :value="p.id">
            {{ p.name }}{{ p.sku ? ` · ${p.sku}` : '' }}
          </option>
        </select>
      </label>

      <label class="field">
        <span>
          Miqdor
          <i class="required">*</i>
          <small v-if="form.movement_type === 'adjust'">(manfiy son ham kiritish mumkin)</small>
        </span>
        <input
          v-model="form.quantity"
          type="number"
          :min="form.movement_type === 'adjust' ? undefined : '0.001'"
          step="0.001"
          required
        />
      </label>

      <label class="field">
        <span>Birlik</span>
        <input
          type="text"
          readonly
          :value="
            selectedProduct
              ? { piece: 'dona', kg: 'kg', liter: 'litr', pack: 'paket' }[selectedProduct.unit]
              : '—'
          "
        />
      </label>

      <label class="field field--full">
        <span>Izoh</span>
        <textarea
          v-model.trim="form.note"
          maxlength="255"
          rows="2"
          placeholder="Sabab haqida qisqacha (masalan: 'Buzilgan paket', 'Inventarizatsiya farqi')"
        />
      </label>

      <p v-if="apiError" class="form-message form-message--error field--full">{{ apiError }}</p>
      <p v-if="successMsg" class="form-message form-message--success field--full">{{ successMsg }}</p>

      <div class="form-actions field--full">
        <button type="button" class="btn btn--ghost" @click="router.push('/app/inventory')">
          Bekor qilish
        </button>
        <button type="submit" class="btn btn--primary" :disabled="saving">
          {{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.adj-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  padding: 18px;
}

.field--full {
  grid-column: 1 / -1;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

@media (max-width: 640px) {
  .adj-form {
    grid-template-columns: 1fr;
  }
}
</style>
