<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import AppPreferencesBar from './AppPreferencesBar.vue'
import BrandLogo from './BrandLogo.vue'
import CashierLayout from './CashierLayout.vue'
import SupportModeBanner from './SupportModeBanner.vue'
import { POS_SHELL_QUERY_KEY, POS_SHELL_QUERY_VALUE } from '../posShellQuery'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { useOrganizationStore } from '../stores/organization'
import { logout as logoutService } from '../services/auth.service'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const org = useOrganizationStore()
const { tr, branchLabel, locale } = useI18n()

const navOpen = ref(false)
const userMenuOpen = ref(false)
const isLoading = ref(true)

/** POS tablari: `?pos=1` bilan kassa shell ichida qoladigan yo‘llar. */
const POS_TAB_PATH_PREFIXES = [
  '/app/sales',
  '/app/products',
  '/app/debtors',
  '/app/inventory/receipt',
  '/app/categories',
]

function pathMatchesPosTab(path) {
  return POS_TAB_PATH_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`))
}

function adminUsesPosShell(currentRoute) {
  const path = currentRoute.path
  if (path === '/app/pos' || path.startsWith('/app/pos/')) return true
  const q = currentRoute.query[POS_SHELL_QUERY_KEY]
  if (q === POS_SHELL_QUERY_VALUE || q === 'true') {
    return pathMatchesPosTab(path)
  }
  return false
}

const useCashierShell = computed(() => {
  if (!auth.loaded) return true
  if (!auth.isAdmin) return true
  return adminUsesPosShell(route)
})

const navGroups = computed(() => [
  {
    label: tr('app.nav.group.main'),
    items: [
      { to: '/app', label: tr('app.nav.dashboard'), icon: '\u25A3' },
      { to: '/app/sales', label: tr('app.nav.sales'), icon: '\u25A7' },
      { to: '/app/debtors', label: tr('app.nav.debtors'), icon: '\u25C8' },
    ],
  },
  {
    label: tr('app.nav.group.catalog'),
    items: [
      { to: '/app/products', label: tr('app.nav.products'), icon: '\u25A2' },
      { to: '/app/categories', label: tr('app.nav.categories'), icon: '\u25A4' },
    ],
  },
  {
    label: tr('app.nav.group.inventory'),
    items: [
      { to: '/app/inventory', label: tr('app.nav.inventory'), icon: '\u25A1' },
      { to: '/app/inventory/receipt', label: tr('app.nav.receipt'), icon: '\u25B2' },
      { to: '/app/inventory/adjust', label: tr('app.nav.adjust'), icon: '\u25BC' },
      { to: '/app/inventory/movements', label: tr('app.nav.movements'), icon: '\u25E6' },
    ],
  },
  {
    label: tr('app.nav.group.reports'),
    items: [{ to: '/app/reports', label: tr('app.nav.reports'), icon: '\u25CE' }],
  },
  {
    label: tr('app.nav.group.settings'),
    items: [
      { to: '/app/users', label: tr('app.nav.users'), icon: '\u25CB' },
      { to: '/app/branches', label: tr('app.nav.branches'), icon: '\u25C7' },
      { to: '/app/billing', label: tr('app.nav.billing'), icon: '\u25C9' },
    ],
  },
])

const SELLER_ALLOWED_PATHS = [
  '/app/pos',
  '/app/sales',
  '/app/products',
  '/app/categories',
  '/app/debtors',
  '/app/inventory/receipt',
]

function isSellerAllowed(path) {
  return SELLER_ALLOWED_PATHS.some((p) => path === p || path.startsWith(p + '/'))
}

onMounted(async () => {
  try {
    const { bootAuthenticatedApp } = await import('../offline/sessionBootstrap')
    const result = await bootAuthenticatedApp(auth, org)
    if (!result.ok) {
      router.push('/auth/login')
      return
    }
    if (auth.isSeller && !isSellerAllowed(router.currentRoute.value.path)) {
      router.replace('/app/pos')
    }
  } catch {
    if (!auth.isAuthenticated) {
      router.push('/auth/login')
    } else {
      const { bootstrapOfflineSession } = await import('../offline/sessionBootstrap')
      await bootstrapOfflineSession(auth, org)
    }
  } finally {
    isLoading.value = false
  }
})

function onBranchChange(event) {
  org.setCurrentBranch(Number(event.target.value))
}

async function logout() {
  userMenuOpen.value = false
  await logoutService()
  auth.reset()
  org.reset()
  router.push('/auth/login')
}
</script>

<template>
  <div v-if="isLoading" class="app-boot">
    <div class="app-boot__inner">{{ tr('app.boot.loading') }}</div>
  </div>

  <template v-else-if="useCashierShell">
    <SupportModeBanner />
    <CashierLayout />
  </template>

  <div v-else class="app-layout-wrap">
    <SupportModeBanner />
    <div class="app-shell" :class="{ 'is-nav-open': navOpen }">
    <aside class="app-sidebar">
      <RouterLink
        to="/app/pos"
        class="app-brand"
        :aria-label="tr('posShell.logoToPos')"
        @click="navOpen = false"
      >
        <BrandLogo variant="sidebar" />
      </RouterLink>

      <nav class="app-nav" :key="locale">
        <div v-for="group in navGroups" :key="group.label" class="app-nav__group">
          <span class="app-nav__group-label">{{ group.label }}</span>
          <RouterLink
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="app-nav__item"
            active-class="is-active"
            :exact-active-class="item.to === '/app' ? 'is-active' : ''"
            @click="navOpen = false"
          >
            <span class="app-nav__icon">{{ item.icon }}</span>
            <span>{{ item.label }}</span>
          </RouterLink>
        </div>
      </nav>

      <div class="app-sidebar__foot">
        <div class="plan-tag" v-if="org.plan">
          <span :class="['plan-tag__chip', `plan-tag__chip--${org.plan.code}`]">
            {{ org.plan.name }}
          </span>
          <RouterLink to="/app/billing">{{ tr('app.plan.manage') }}</RouterLink>
        </div>
      </div>
    </aside>

    <div class="app-main">
      <header class="app-topbar">
        <button class="app-topbar__nav-toggle" type="button" @click="navOpen = !navOpen">
          ☰
        </button>
        <div class="app-topbar__org">
          <strong>{{ org.organization?.name || tr('app.orgFallback') }}</strong>
          <div class="app-topbar__tools">
            <select
              v-if="org.branches.length"
              class="branch-picker"
              :value="org.currentBranchId || ''"
              @change="onBranchChange"
            >
              <option v-for="b in org.branches" :key="b.id" :value="b.id">
                {{ branchLabel(b) }}
              </option>
            </select>
            <RouterLink
              to="/app/pos"
              class="app-topbar__sales"
              :title="tr('app.topbar.toSalesTitle')"
            >
              <span class="app-topbar__sales-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <circle cx="9" cy="21" r="1.5" />
                  <circle cx="18" cy="21" r="1.5" />
                  <path d="M2 3h2.5l3.6 13.4a2 2 0 0 0 2 1.6h9.4a2 2 0 0 0 2-1.5L23 7H6" />
                </svg>
              </span>
              <span class="app-topbar__sales-text">{{ tr('app.topbar.toSales') }}</span>
            </RouterLink>
          </div>
        </div>

        <div class="app-topbar__spacer" />

        <div class="app-topbar__tail">
          <AppPreferencesBar />
          <div class="user-menu" @click.stop="userMenuOpen = !userMenuOpen">
          <span class="user-menu__avatar">{{ auth.initials || '?' }}</span>
          <div class="user-menu__meta">
            <strong>{{ auth.fullName }}</strong>
            <small>{{ auth.role || 'role' }}</small>
          </div>
          <span class="user-menu__caret">▾</span>
          <div v-if="userMenuOpen" class="user-menu__dropdown" @click.stop>
            <RouterLink to="/app" @click="userMenuOpen = false">{{ tr('app.user.dashboard') }}</RouterLink>
            <RouterLink to="/app/users" @click="userMenuOpen = false">{{ tr('app.user.staff') }}</RouterLink>
            <RouterLink to="/app/billing" @click="userMenuOpen = false">{{ tr('app.user.billing') }}</RouterLink>
            <button type="button" @click="logout">{{ tr('app.user.logout') }}</button>
          </div>
        </div>
        </div>
      </header>

      <main class="app-content">
        <RouterView />
      </main>
    </div>

    <div v-if="navOpen" class="app-shell__backdrop" @click="navOpen = false" />
    </div>
  </div>
</template>

<style scoped>
.app-boot {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #f3f4f6;
  color: #4b5563;
  font-size: 0.95rem;
}
.app-boot__inner {
  padding: 24px 32px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.08);
}
</style>
