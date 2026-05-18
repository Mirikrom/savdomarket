<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

import AppModal from '../../components/AppModal.vue'
import DataTable from '../../components/DataTable.vue'
import PageHeader from '../../components/PageHeader.vue'
import { organizationUsers, roles } from '../../services/users.service'
import { useAuthStore } from '../../stores/auth'
import { useOrganizationStore } from '../../stores/organization'

const auth = useAuthStore()
const org = useOrganizationStore()

const rows = ref([])
const rolesList = ref([])
const loading = ref(true)

const inviteOpen = ref(false)
const editOpen = ref(false)
const editingId = ref(null)
const saving = ref(false)
const apiError = ref('')
const tempCredentials = ref(null) // { phone, password } shown after invite

const inviteForm = reactive({
  phone: '',
  full_name: '',
  role_id: '',
  branch_id: '',
})

const editForm = reactive({
  role_id: '',
  branch_id: '',
  status: 'active',
})

const ROLE_LABELS = {
  owner: 'Egasi',
  admin: 'Administrator',
  moderator: 'Moderator',
  cashier: 'Kassir',
  seller: 'Sotuvchi',
}

const STATUS_LABELS = {
  active: 'Faol',
  invited: 'Taklif qilingan',
  suspended: 'To‘xtatilgan',
}

// Hide system "owner" role from the picker — there can be only one and it's
// the registering user. Other roles (admin/moderator/cashier/seller) are
// available for hiring employees.
const assignableRoles = computed(() =>
  rolesList.value.filter((r) => r.code !== 'owner'),
)

const columns = [
  { key: 'user_detail', label: 'Xodim' },
  { key: 'role_chip', label: 'Rol', width: '140px' },
  { key: 'branch', label: 'Filial', width: '140px' },
  { key: 'status', label: 'Holat', width: '110px' },
]

function formatBranch(branchId) {
  if (!branchId) return '—'
  return org.branches.find((b) => b.id === branchId)?.name || '—'
}

function userLabel(detail) {
  if (!detail) return '—'
  return `${detail.full_name || ''} (${detail.phone || ''})`
}

function initials(detail) {
  const name = detail?.full_name || detail?.phone || ''
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0])
    .join('')
    .toUpperCase() || '?'
}

async function fetchData() {
  loading.value = true
  try {
    const [members, allRoles] = await Promise.all([
      organizationUsers.list(),
      roles.list(),
    ])
    rows.value = members
    rolesList.value = allRoles
  } finally {
    loading.value = false
  }
}

function openInvite() {
  apiError.value = ''
  tempCredentials.value = null
  inviteForm.phone = ''
  inviteForm.full_name = ''
  inviteForm.role_id =
    assignableRoles.value.find((r) => r.code === 'cashier')?.id || assignableRoles.value[0]?.id || ''
  inviteForm.branch_id = org.currentBranchId || ''
  inviteOpen.value = true
}

async function submitInvite() {
  apiError.value = ''
  saving.value = true
  try {
    const payload = {
      phone: inviteForm.phone,
      full_name: inviteForm.full_name,
      role_id: Number(inviteForm.role_id),
    }
    if (inviteForm.branch_id) payload.branch_id = Number(inviteForm.branch_id)

    const result = await organizationUsers.invite(payload)
    await fetchData()

    if (result.user_created && result.temporary_password) {
      tempCredentials.value = {
        phone: result.membership?.user_detail?.phone,
        password: result.temporary_password,
      }
    } else {
      inviteOpen.value = false
    }
  } catch (error) {
    const data = error?.response?.data
    apiError.value =
      data?.detail ||
      (typeof data === 'object' ? Object.values(data)?.[0]?.[0] : '') ||
      'Xodim qo‘shishda xatolik.'
  } finally {
    saving.value = false
  }
}

function openEdit(row) {
  editingId.value = row.id
  editForm.role_id = row.role
  editForm.branch_id = row.branch || ''
  editForm.status = row.status
  apiError.value = ''
  editOpen.value = true
}

async function submitEdit() {
  apiError.value = ''
  saving.value = true
  try {
    await organizationUsers.update(editingId.value, {
      role: Number(editForm.role_id),
      branch: editForm.branch_id ? Number(editForm.branch_id) : null,
      status: editForm.status,
    })
    editOpen.value = false
    await fetchData()
  } catch (error) {
    const data = error?.response?.data
    apiError.value =
      data?.detail ||
      (typeof data === 'object' ? Object.values(data)?.[0]?.[0] : '') ||
      'Saqlashda xatolik.'
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  if (row.user_detail?.phone === auth.user?.phone) {
    alert('O‘zingizni o‘chira olmaysiz.')
    return
  }
  if (!confirm(`"${row.user_detail?.full_name}" tashkilotdan chiqarilsinmi?`)) return
  try {
    await organizationUsers.remove(row.id)
    await fetchData()
  } catch (error) {
    alert(error?.response?.data?.detail || 'O‘chirib bo‘lmadi.')
  }
}

function copyCredentials() {
  if (!tempCredentials.value) return
  const text = `Telefon: ${tempCredentials.value.phone}\nVaqtinchalik parol: ${tempCredentials.value.password}`
  navigator.clipboard?.writeText(text)
}

function closeInvite() {
  inviteOpen.value = false
  tempCredentials.value = null
}

onMounted(fetchData)
</script>

<template>
  <div>
    <PageHeader
      title="Xodimlar"
      subtitle="Tashkilotga biriktirilgan foydalanuvchilar va ularning rollari"
    >
      <template #actions>
        <button class="btn btn--primary" @click="openInvite">+ Yangi xodim</button>
      </template>
    </PageHeader>

    <DataTable
      :columns="columns"
      :rows="rows"
      :loading="loading"
      empty-text="Hozircha xodimlar qo‘shilmagan."
    >
      <template #cell:user_detail="{ row }">
        <div class="user-cell">
          <span class="user-cell__avatar">{{ initials(row.user_detail) }}</span>
          <div class="user-cell__meta">
            <strong>{{ row.user_detail?.full_name || '—' }}</strong>
            <small>{{ row.user_detail?.phone || '' }}</small>
          </div>
        </div>
      </template>

      <template #cell:role_chip="{ row }">
        <span :class="['role-chip', `role-chip--${rolesList.find((r) => r.id === row.role)?.code || 'unknown'}`]">
          {{ ROLE_LABELS[rolesList.find((r) => r.id === row.role)?.code] || rolesList.find((r) => r.id === row.role)?.name || '—' }}
        </span>
      </template>

      <template #cell:branch="{ row }">{{ formatBranch(row.branch) }}</template>

      <template #cell:status="{ row }">
        <span :class="['status-chip', `status-chip--${row.status}`]">
          {{ STATUS_LABELS[row.status] || row.status }}
        </span>
      </template>

      <template #actions="{ row }">
        <button class="icon-btn" @click="openEdit(row)">Tahrirlash</button>
        <button class="icon-btn icon-btn--danger" @click="remove(row)">Chiqarish</button>
      </template>
    </DataTable>

    <p class="hint-text">
      Eslatma: Yangi xodim qo‘shilganda, tizim avtomatik vaqtinchalik parol yaratadi. Uni xodimga
      og‘zaki yetkazing — keyin xodim o‘zi parolini o‘zgartirishi kerak.
    </p>

    <AppModal
      :open="inviteOpen"
      title="Yangi xodim qo'shish"
      width="540px"
      @close="closeInvite"
    >
      <div v-if="tempCredentials" class="cred-card">
        <h4>✓ Xodim yaratildi</h4>
        <p>Foydalanuvchiga quyidagi ma'lumotlarni bering:</p>
        <div class="cred-row">
          <strong>Telefon:</strong>
          <span>{{ tempCredentials.phone }}</span>
        </div>
        <div class="cred-row">
          <strong>Vaqtinchalik parol:</strong>
          <code>{{ tempCredentials.password }}</code>
        </div>
        <button class="btn btn--ghost btn--sm" type="button" @click="copyCredentials">
          Nusxa olish
        </button>
        <p class="hint-text" style="margin-top: 8px">
          Bu parol faqat hozir ko‘rinadi. Xodim birinchi marta kirgandan keyin o‘z parolini
          o‘zgartirishi tavsiya etiladi.
        </p>
      </div>

      <form v-else class="form-grid" @submit.prevent="submitInvite">
        <label class="field field--full">
          <span>Telefon raqam <i class="required">*</i></span>
          <input
            v-model.trim="inviteForm.phone"
            type="tel"
            placeholder="+998 90 123 45 67"
            required
          />
        </label>

        <label class="field field--full">
          <span>To'liq ism <i class="required">*</i></span>
          <input v-model.trim="inviteForm.full_name" type="text" required maxlength="255" />
        </label>

        <label class="field">
          <span>Rol <i class="required">*</i></span>
          <select v-model="inviteForm.role_id" required>
            <option value="">— Tanlang —</option>
            <option v-for="r in assignableRoles" :key="r.id" :value="r.id">
              {{ ROLE_LABELS[r.code] || r.name }}
            </option>
          </select>
        </label>

        <label class="field">
          <span>Filial</span>
          <select v-model="inviteForm.branch_id">
            <option value="">— Hammasi —</option>
            <option v-for="b in org.branches" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
        </label>

        <p v-if="apiError" class="form-message form-message--error field--full">
          {{ apiError }}
        </p>
      </form>

      <template #footer>
        <template v-if="tempCredentials">
          <button class="btn btn--primary" type="button" @click="closeInvite">Yopish</button>
        </template>
        <template v-else>
          <button class="btn btn--ghost" type="button" @click="closeInvite">Bekor qilish</button>
          <button class="btn btn--primary" :disabled="saving" @click="submitInvite">
            {{ saving ? 'Yaratilmoqda...' : 'Yaratish' }}
          </button>
        </template>
      </template>
    </AppModal>

    <AppModal :open="editOpen" title="Xodimni tahrirlash" @close="editOpen = false">
      <form class="auth-form" @submit.prevent="submitEdit">
        <label class="field">
          <span>Rol</span>
          <select v-model="editForm.role_id">
            <option v-for="r in assignableRoles" :key="r.id" :value="r.id">
              {{ ROLE_LABELS[r.code] || r.name }}
            </option>
          </select>
        </label>
        <label class="field">
          <span>Filial</span>
          <select v-model="editForm.branch_id">
            <option value="">— Hammasi —</option>
            <option v-for="b in org.branches" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
        </label>
        <label class="field">
          <span>Holat</span>
          <select v-model="editForm.status">
            <option value="active">Faol</option>
            <option value="suspended">To‘xtatilgan</option>
          </select>
        </label>
        <p v-if="apiError" class="form-message form-message--error">{{ apiError }}</p>
      </form>
      <template #footer>
        <button class="btn btn--ghost" type="button" @click="editOpen = false">Bekor qilish</button>
        <button class="btn btn--primary" :disabled="saving" @click="submitEdit">
          {{ saving ? 'Saqlanmoqda...' : 'Saqlash' }}
        </button>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.user-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.user-cell__avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1f4fa3, #4a85e0);
  color: #ffffff;
  font-weight: 700;
  display: grid;
  place-items: center;
  font-size: 0.78rem;
  flex-shrink: 0;
}

.user-cell__meta {
  display: flex;
  flex-direction: column;
  line-height: 1.15;
}

.user-cell__meta small {
  color: var(--text-muted);
  font-size: 0.78rem;
}

.role-chip,
.status-chip {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.role-chip--owner {
  background: #fff4d6;
  color: #8a5a00;
}
.role-chip--admin {
  background: #e3eaff;
  color: #1f4fa3;
}
.role-chip--moderator {
  background: #e7f5ec;
  color: #1f7a48;
}
.role-chip--cashier {
  background: #fff2e8;
  color: #b3490d;
}
.role-chip--seller {
  background: #f0e8ff;
  color: #5b21b6;
}
.role-chip--unknown {
  background: var(--surface-soft);
  color: var(--text-muted);
}

.status-chip--active {
  background: #effcf8;
  color: var(--success);
}
.status-chip--invited {
  background: #eef4ff;
  color: var(--primary);
}
.status-chip--suspended {
  background: #fdeef0;
  color: var(--danger);
}

.hint-text {
  margin-top: 14px;
  color: var(--text-muted);
  font-size: 0.86rem;
}

.cred-card {
  background: #effcf8;
  border: 1px solid #b8efe2;
  border-radius: var(--radius-md);
  padding: 16px 18px;
  display: grid;
  gap: 8px;
}

.cred-card h4 {
  margin: 0;
  color: var(--success);
  font-size: 1rem;
}

.cred-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  font-size: 0.95rem;
}

.cred-row code {
  background: #ffffff;
  border: 1px solid var(--line);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", monospace;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text);
  user-select: all;
}
</style>
