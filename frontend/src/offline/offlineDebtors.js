import { debtors as debtorsApi } from '../services/debtors.service'
import { isOfflineMode } from './connectivity'
import { loadDebtorsFromIndexedDB } from './fullSync'
import { normalizeOrgId, savdoDb, toPlainJson } from './db'
import { applyOfflineLedgerToDebtor, getOfflineDebtorLedger } from './offlineDebtLedger'
import {
  isLocalDebtorRef,
  LOCAL_DEBTOR_PREFIX,
  localDebtorRef,
} from './offlineDebtorIds'
import { newClientUuid } from './offlineSales'

export { isLocalDebtorRef, LOCAL_DEBTOR_PREFIX, localDebtorRef }

export async function createOfflineDebtor(organizationId, { name, phone = '', note = '', due_date = null }) {
  const orgId = normalizeOrgId(organizationId)
  const client_uuid = newClientUuid()
  const row = toPlainJson({
    client_uuid,
    status: 'pending',
    organizationId: orgId,
    name: String(name || '').trim(),
    phone: String(phone || '').trim(),
    note: String(note || '').trim(),
    due_date: due_date || null,
    server_id: null,
    balance_due: 0,
    is_active: true,
    created_at: Date.now(),
  })

  await savdoDb.local_debtors.put(row)

  await savdoDb.debtors.put(
    toPlainJson({
      id: localDebtorRef(client_uuid),
      organizationId: orgId,
      name: row.name,
      phone: row.phone,
      note: row.note,
      due_date: row.due_date || null,
      balance_due: 0,
      total_credit: 0,
      total_paid: 0,
      is_active: true,
      _offlinePending: true,
      _client_uuid: client_uuid,
    })
  )

  return row
}

export async function loadDebtorsMerged(organizationId) {
  const orgId = normalizeOrgId(organizationId)
  if (!orgId) return []

  const cached = await loadDebtorsFromIndexedDB(orgId)
  const pending = await savdoDb.local_debtors.where('status').equals('pending').toArray()
  const pendingOnly = pending.filter((p) => Number(p.organizationId) === orgId)

  const seen = new Set(cached.map((d) => String(d.id)))
  const extra = pendingOnly
    .filter((p) => !seen.has(localDebtorRef(p.client_uuid)))
    .map((p) => ({
      id: localDebtorRef(p.client_uuid),
      organizationId: orgId,
      name: p.name,
      phone: p.phone || '',
      note: p.note || '',
      due_date: p.due_date || null,
      balance_due: Number(p.balance_due || 0),
      total_credit: 0,
      total_paid: 0,
      is_active: true,
      _offlinePending: true,
      _client_uuid: p.client_uuid,
    }))

  const merged = [...cached, ...extra]
  const ledger = await getOfflineDebtorLedger(orgId)
  return merged
    .map((d) => applyOfflineLedgerToDebtor(d, ledger))
    .sort((a, b) => (a.name || '').localeCompare(b.name || '', 'uz'))
}

export async function syncOfflineDebtors() {
  if (isOfflineMode()) return { synced: 0, failed: 0, skipped: true }

  const pending = await savdoDb.local_debtors.where('status').equals('pending').toArray()
  pending.sort((a, b) => (a.created_at || 0) - (b.created_at || 0))

  let synced = 0
  let failed = 0

  for (const row of pending) {
    try {
      const created = await debtorsApi.create({
        name: row.name,
        phone: row.phone || '',
        note: row.note || '',
        due_date: row.due_date || null,
        client_uuid: row.client_uuid,
      })
      await savdoDb.local_debtors.update(row.client_uuid, {
        status: 'synced',
        server_id: created.id,
        synced_at: Date.now(),
      })

      await savdoDb.debtors.delete(localDebtorRef(row.client_uuid))
      await savdoDb.debtors.put(
        toPlainJson({
          ...created,
          organizationId: row.organizationId,
        })
      )
      synced += 1
    } catch (err) {
      console.warn('[offline] qarzdor sinxron:', row.client_uuid, err?.response?.data || err?.message)
      failed += 1
      if (!err?.response) break
    }
  }

  return { synced, failed }
}

export async function resolveDebtorServerId(debtorRef, debtorClientUuid) {
  if (debtorRef && Number(debtorRef) > 0) return Number(debtorRef)

  let uuid = debtorClientUuid
  if (!uuid && isLocalDebtorRef(debtorRef)) {
    uuid = debtorRef.slice(LOCAL_DEBTOR_PREFIX.length)
  }
  if (!uuid) return null

  const local = await savdoDb.local_debtors.get(uuid)
  if (local?.server_id) return local.server_id

  await syncOfflineDebtors()
  const again = await savdoDb.local_debtors.get(uuid)
  return again?.server_id || null
}
