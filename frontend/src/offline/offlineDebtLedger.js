import { isLocalDebtorRef, localDebtorRef } from './offlineDebtorIds'
import { normalizeOrgId, savdoDb } from './db'

/** Offline qarzga savdodan qolgan summa (to'langan qismi hisobga olinadi). */
export function salePayloadCreditAmount(payload) {
  if (!payload) return 0
  let subtotal = 0
  for (const line of payload.items || []) {
    subtotal += Number(line.quantity || 0) * Number(line.unit_price || 0)
  }
  const discount = Number(payload.discount || 0)
  const total = Math.max(0, subtotal - discount)
  const paid = (payload.payments || []).reduce((s, p) => s + Number(p.amount || 0), 0)
  return Math.max(0, total - paid)
}

function debtorRefFromSaleRow(row) {
  const p = row.payload || {}
  if (row.debtor_client_uuid) return localDebtorRef(row.debtor_client_uuid)
  if (p.debtor && Number(p.debtor) > 0) return String(Number(p.debtor))
  return null
}

export async function getOfflineDebtorLedger(organizationId) {
  const orgId = normalizeOrgId(organizationId)
  const creditByRef = new Map()
  const paymentByRef = new Map()
  const pendingRefs = new Set()

  if (!orgId) {
    return { creditByRef, paymentByRef, pendingRefs }
  }

  const pendingSales = await savdoDb.local_sales.where('status').equals('pending').toArray()
  for (const row of pendingSales) {
    const ref = debtorRefFromSaleRow(row)
    if (!ref) continue
    const credit = salePayloadCreditAmount(row.payload)
    if (credit <= 0) continue
    creditByRef.set(ref, (creditByRef.get(ref) || 0) + credit)
    pendingRefs.add(ref)
  }

  const pendingPayments = await savdoDb.local_debt_payments
    .where('status')
    .equals('pending')
    .toArray()
  for (const row of pendingPayments) {
    if (Number(row.organizationId) !== orgId) continue
    const ref = String(row.debtor_ref || '')
    if (!ref) continue
    paymentByRef.set(ref, (paymentByRef.get(ref) || 0) + Number(row.amount || 0))
    pendingRefs.add(ref)
  }

  const pendingDebtors = await savdoDb.local_debtors.where('status').equals('pending').toArray()
  for (const row of pendingDebtors) {
    if (Number(row.organizationId) === orgId) {
      pendingRefs.add(localDebtorRef(row.client_uuid))
    }
  }

  return { creditByRef, paymentByRef, pendingRefs }
}

export function applyOfflineLedgerToDebtor(debtor, ledger) {
  const ref = String(debtor.id)
  const credit = ledger.creditByRef.get(ref) || 0
  const paidOffline = ledger.paymentByRef.get(ref) || 0
  const balance = Math.max(
    0,
    Number(debtor.balance_due || 0) + credit - paidOffline,
  )
  const hasPending =
    ledger.pendingRefs.has(ref) ||
    (Boolean(debtor._offlinePending) && isLocalDebtorRef(ref))

  return {
    ...debtor,
    balance_due: balance,
    total_credit: Number(debtor.total_credit || 0) + credit,
    total_paid: Number(debtor.total_paid || 0) + paidOffline,
    _syncStatus: hasPending ? 'pending' : 'synced',
  }
}
