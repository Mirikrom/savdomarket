<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import PageHeader from '../../components/PageHeader.vue'
import { useI18n } from '../../i18n'
import { products as productsApi } from '../../services/catalog.service'
import { stockMovements } from '../../services/inventory.service'
import { routeWithPosShell } from '../../posShellQuery'
import { useAuthStore } from '../../stores/auth'
import { useOrganizationStore } from '../../stores/organization'

const router = useRouter()
const auth = useAuthStore()
const org = useOrganizationStore()
const { tr } = useI18n()

const productList = ref([])
const loading = ref(true)
const saving = ref(false)
const apiError = ref('')
const successMsg = ref('')

const form = reactive({
  branch: '',
  note: '',
  items: [createLine()],
})

function createLine() {
  return {
    product: '',
    quantity: '1',
    unit_cost: '0',
  }
}

const productMap = computed(() => {
  const map = {}
  for (const p of productList.value) map[p.id] = p
  return map
})

const totalCost = computed(() => {
  return form.items.reduce((sum, item) => {
    const q = Number(item.quantity || 0)
    const c = Number(item.unit_cost || 0)
    return sum + q * c
  }, 0)
})

async function fetchProducts() {
  loading.value = true
  try {
    productList.value = await productsApi.list()
  } finally {
    loading.value = false
  }
}

function addLine() {
  form.items.push(createLine())
}

function removeLine(index) {
  if (form.items.length === 1) {
    form.items[0] = createLine()
    return
  }
  form.items.splice(index, 1)
}

function getUnit(productId) {
  const p = productMap.value[productId]
  if (!p) return ''
  return {
    piece: 'dona',
    kg: 'kg',
    liter: 'litr',
    pack: 'paket',
  }[p.unit] || ''
}

async function submit() {
  apiError.value = ''
  successMsg.value = ''

  if (!form.branch) {
    apiError.value = 'Filialni tanlang.'
    return
  }
  const validItems = form.items.filter((i) => i.product && Number(i.quantity) > 0)
  if (validItems.length === 0) {
    apiError.value = 'Hech bo‘lmaganda bitta mahsulot kiriting.'
    return
  }

  saving.value = true
  try {
    const payload = {
      branch: Number(form.branch),
      note: form.note,
      items: validItems.map((i) => ({
        product: Number(i.product),
        quantity: i.quantity,
        unit_cost: i.unit_cost || 0,
      })),
    }
    const res = await stockMovements.bulkIn(payload)
    successMsg.value = `Muvaffaqiyatli kirim qilindi: ${res.created} ta qator`
    form.items = [createLine()]
    form.note = ''
  } catch (error) {
    const data = error?.response?.data
    apiError.value =
      data?.detail ||
      (typeof data === 'object' ? JSON.stringify(data) : '') ||
      'Kirim qilishda xatolik.'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await fetchProducts()
  if (org.currentBranchId) form.branch = String(org.currentBranchId)
})

function resetForm() {
  apiError.value = ''
  successMsg.value = ''
  form.note = ''
  form.items = [createLine()]
  if (org.currentBranchId) form.branch = String(org.currentBranchId)
  else form.branch = ''
}

/** Sotuvchi — kassaga; boshqaruvchi — qoldiqlar ro‘yxatiga. */
function leaveReceipt() {
  if (auth.isSeller) {
    router.push(routeWithPosShell('/app/pos'))
    return
  }
  router.push('/app/inventory')
}
</script>

<template>
  <div>
    <PageHeader :title="tr('page.receipt.title')" :subtitle="tr('page.receipt.subtitle')">
      <template #actions>
        <button type="button" class="btn btn--ghost" @click="leaveReceipt">
          {{ auth.isSeller ? '← Kassa' : '← Qoldiqlarga' }}
        </button>
      </template>
    </PageHeader>

    <form class="receipt-form" @submit.prevent="submit">
      <div class="card head-card">
        <label class="field">
          <span>Qaysi filialga? <i class="required">*</i></span>
          <select v-model="form.branch" required>
            <option value="" disabled>— Filial tanlang —</option>
            <option v-for="b in org.branches" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>Izoh (ixtiyoriy)</span>
          <input
            v-model.trim="form.note"
            type="text"
            maxlength="255"
            placeholder="Masalan, Yetkazib beruvchi nomi yoki invoice raqami"
          />
        </label>
      </div>

      <div class="card">
        <div class="receipt-head">
          <h3>Mahsulotlar</h3>
          <button type="button" class="btn btn--ghost btn--sm" @click="addLine">+ Qator</button>
        </div>

        <div v-if="loading" class="data-table__placeholder">Yuklanmoqda...</div>
        <div v-else-if="productList.length === 0" class="data-table__placeholder">
          Avval katalogga mahsulot qo‘shing.
          <RouterLink to="/app/products">Mahsulotlar sahifasi →</RouterLink>
        </div>

        <div v-else class="receipt-lines">
          <div v-for="(line, idx) in form.items" :key="idx" class="receipt-line">
            <div class="receipt-line__num">{{ idx + 1 }}</div>

            <label class="field field--grow">
              <span>Mahsulot</span>
              <select v-model="line.product">
                <option value="" disabled>— Tanlang —</option>
                <option v-for="p in productList" :key="p.id" :value="p.id">
                  {{ p.name }}{{ p.sku ? ` · ${p.sku}` : '' }}
                </option>
              </select>
            </label>

            <label class="field field--qty">
              <span>Miqdor <small>({{ getUnit(line.product) || '—' }})</small></span>
              <input v-model="line.quantity" type="number" min="0.001" step="0.001" />
            </label>

            <label class="field field--price">
              <span>Tannarx (so‘m)</span>
              <input v-model="line.unit_cost" type="number" min="0" step="0.01" />
            </label>

            <div class="field field--total">
              <span>Jami</span>
              <strong>
                {{
                  (Number(line.quantity || 0) * Number(line.unit_cost || 0)).toLocaleString(
                    'uz-UZ',
                    { maximumFractionDigits: 2 },
                  )
                }}
              </strong>
            </div>

            <button
              type="button"
              class="icon-btn icon-btn--danger receipt-line__remove"
              @click="removeLine(idx)"
            >
              ×
            </button>
          </div>
        </div>

        <div class="receipt-foot">
          <div class="receipt-foot__total">
            <span>Umumiy summa:</span>
            <strong>{{ totalCost.toLocaleString('uz-UZ', { maximumFractionDigits: 2 }) }} so‘m</strong>
          </div>
        </div>
      </div>

      <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      <p v-if="successMsg" class="form-message form-message--success">{{ successMsg }}</p>

      <div class="form-actions">
        <button type="button" class="btn btn--ghost" @click="resetForm">
          Bekor qilish
        </button>
        <button type="submit" class="btn btn--primary" :disabled="saving">
          {{ saving ? 'Saqlanmoqda...' : 'Kirimni saqlash' }}
        </button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.receipt-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.head-card {
  display: grid;
  grid-template-columns: 1fr 1.5fr;
  gap: 14px;
  padding: 14px 16px;
}

.receipt-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}

.receipt-head h3 {
  margin: 0;
  font-size: 1rem;
}

.receipt-lines {
  display: flex;
  flex-direction: column;
}

.receipt-line {
  display: grid;
  grid-template-columns: 32px 2fr 0.8fr 1fr 1fr 36px;
  gap: 10px;
  padding: 12px 16px;
  align-items: end;
  border-bottom: 1px solid var(--line);
}

.receipt-line:last-child {
  border-bottom: 0;
}

.receipt-line__num {
  font-weight: 600;
  color: var(--text-muted);
  padding-bottom: 10px;
}

.field--grow {
  min-width: 0;
}

.field--total {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: 8px;
  text-align: right;
}

.field--total span {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.receipt-line__remove {
  align-self: end;
  margin-bottom: 4px;
}

.receipt-foot {
  display: flex;
  justify-content: flex-end;
  padding: 14px 16px;
  border-top: 1px solid var(--line);
  background: var(--surface-soft);
}

.receipt-foot__total {
  font-size: 1rem;
  display: flex;
  gap: 12px;
  align-items: center;
}

.receipt-foot__total strong {
  font-size: 1.2rem;
  color: var(--text);
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

@media (max-width: 720px) {
  .head-card {
    grid-template-columns: 1fr;
  }
  .receipt-line {
    grid-template-columns: 32px 1fr 36px;
    grid-template-areas:
      'num product remove'
      '. qty qty'
      '. price price'
      '. total total';
  }
  .receipt-line__num {
    grid-area: num;
  }
  .receipt-line .field--grow {
    grid-area: product;
  }
  .receipt-line .field--qty {
    grid-area: qty;
  }
  .receipt-line .field--price {
    grid-area: price;
  }
  .receipt-line .field--total {
    grid-area: total;
    text-align: left;
  }
  .receipt-line__remove {
    grid-area: remove;
  }
}
</style>
