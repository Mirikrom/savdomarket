import { createApp } from 'vue'
import { createPinia } from 'pinia'

import './style.css'
import App from './App.vue'
import router from './router'
import { initOfflineSync } from './offline/init'
import { useOrganizationStore } from './stores/organization'
import { useUiStore } from './stores/ui'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

useUiStore(pinia).init()

initOfflineSync(async () => {
  const org = useOrganizationStore(pinia)
  const { hydrateOrganizationStore, resolvePosIds } = await import('./offline/posContext')
  await hydrateOrganizationStore(org)
  const { orgId, branchId } = await resolvePosIds(org)
  return {
    organizationId: orgId,
    branchId,
    branches: org.branches,
    organization: org.organization,
  }
})

app.mount('#app')
