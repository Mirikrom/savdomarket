import { checkApiReachable, onConnectivityChange, resumeConnectivityProbe } from './connectivity'
import { scheduleFullSync, schedulePendingSalesSync } from './syncScheduler'

let listenersBound = false
let probeTimer = null
let wasOffline = false

async function getCtx(getContext) {
  const ctx = await getContext?.()
  if (!ctx) return null
  const orgId = ctx.organizationId ?? Number(localStorage.getItem('organization_id'))
  const branchId = ctx.branchId ?? Number(localStorage.getItem('current_branch_id'))
  if (!orgId || !branchId) return null
  return {
    ...ctx,
    organizationId: orgId,
    branchId,
    organization: ctx.organization ?? null,
  }
}

async function onBackOnline(getContext) {
  const ctx = await getCtx(getContext)
  if (!ctx) return

  await schedulePendingSalesSync()
  await scheduleFullSync(ctx.organizationId, ctx.branchId, {
    branches: ctx.branches,
    organization: ctx.organization,
    force: true,
  })
}

async function probeConnectivity(getContext) {
  const offlineBefore = wasOffline
  const ok = await checkApiReachable()
  wasOffline = !ok

  if (ok && offlineBefore) {
    await onBackOnline(getContext)
  } else if (ok) {
    await schedulePendingSalesSync()
  }
}

export function initOfflineSync(getContext) {
  if (listenersBound || typeof window === 'undefined') return
  listenersBound = true

  wasOffline = typeof navigator !== 'undefined' ? !navigator.onLine : true

  const probe = () => probeConnectivity(getContext)

  window.addEventListener('online', probe)
  window.addEventListener('offline', () => {
    wasOffline = true
    checkApiReachable()
  })

  const runProbeIfVisible = () => {
    if (typeof document !== 'undefined' && document.hidden) return
    probe()
  }

  probe()
  probeTimer = setInterval(runProbeIfVisible, 60000)

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      resumeConnectivityProbe()
      probe()
    }
  })
}

export function stopOfflineProbe() {
  if (probeTimer) {
    clearInterval(probeTimer)
    probeTimer = null
  }
}

export { onConnectivityChange, checkApiReachable }
export { bootAuthenticatedApp, bootstrapOfflineSession } from './sessionBootstrap'
export { scheduleFullSync, schedulePendingSalesSync } from './syncScheduler'
export { syncAllOfflineData } from './fullSync'
export { countPendingSales, syncOfflineSales } from './offlineSales'
