import { debtors as debtorsApi } from '../services/debtors.service'
import { checkApiReachable, isOfflineMode } from './connectivity'
import { getOfflineDebtorLedger } from './offlineDebtLedger'
import { isLocalDebtorRef, LOCAL_DEBTOR_PREFIX } from './offlineDebtorIds'
import { resolveDebtorServerId } from './offlineDebtors'
import { newClientUuid } from './offlineSales'
import { normalizeOrgId, savdoDb, toPlainJson } from './db'

export async function countPendingDebtorSyncItems() {
  const debtors = await savdoDb.local_debtors.where('status').equals('pending').count()
  const payments = await savdoDb.local_debt_payments.where('status').equals('pending').count()
  return debtors + payments
}

export async function saveOfflineDebtPayment(organizationId, debtorRow, payment) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) throw new Error('Tashkilot tanlanmagan')

  const amount = Number(payment.amount || 0)
  if (!Number.isFinite(amount) || amount <= 0) {
    throw new Error('Summa noto‘g‘ri')
  }

  const ledger = await getOfflineDebtorLedger(orgId)
  const ref = String(debtorRow.id)
  const effectiveBalance =
    Number(debtorRow.balance_due || 0) +
    (ledger.creditByRef.get(ref) || 0) -
    (ledger.paymentByRef.get(ref) || 0)

  if (amount > effectiveBalance + 0.0001) {
    throw new Error('Summa qarzdan oshmasligi kerak')
  }

  let debtor_ref = ref
  let debtor_client_uuid = debtorRow._client_uuid || null
  let debtor_server_id = Number(debtorRow.id) > 0 ? Number(debtorRow.id) : null

  if (isLocalDebtorRef(debtor_ref)) {
    debtor_client_uuid = debtor_ref.slice(LOCAL_DEBTOR_PREFIX.length)
    debtor_server_id = null
  }

  const client_uuid = newClientUuid()
  const row = toPlainJson({
    client_uuid,
    status: 'pending',
    organizationId: orgId,
    debtor_ref,
    debtor_client_uuid,
    debtor_server_id,
    branch: Number(payment.branch),
    amount: String(amount),
    method: payment.method || 'cash',
    note: payment.note || '',
    created_at: Date.now(),
  })

  await savdoDb.local_debt_payments.put(row)
  return row
}

export async function syncOfflineDebtPayments() {
  if (isOfflineMode()) {
    const ok = await checkApiReachable()
    if (!ok) return { synced: 0, failed: 0, skipped: true }
  }

  const pending = await savdoDb.local_debt_payments.where('status').equals('pending').toArray()
  pending.sort((a, b) => (a.created_at || 0) - (b.created_at || 0))

  let synced = 0
  let failed = 0

  for (const row of pending) {
    try {
      const debtorId = await resolveDebtorServerId(
        row.debtor_server_id,
        row.debtor_client_uuid,
      )
      if (!debtorId) {
        failed += 1
        continue
      }

      await debtorsApi.pay(debtorId, {
        branch: row.branch,
        amount: row.amount,
        method: row.method,
        note: row.note || '',
        client_uuid: row.client_uuid,
      })

      await savdoDb.local_debt_payments.update(row.client_uuid, {
        status: 'synced',
        synced_at: Date.now(),
      })
      synced += 1
    } catch (err) {
      console.warn(
        '[offline] qarz to‘lovi sinxron:',
        row.client_uuid,
        err?.response?.data || err?.message,
      )
      failed += 1
      if (!err?.response) break
    }
  }

  return { synced, failed }
}
