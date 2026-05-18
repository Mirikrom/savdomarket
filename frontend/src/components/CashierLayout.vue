<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import BrandLogo from './BrandLogo.vue'
import ConnectivityStatusDot from './ConnectivityStatusDot.vue'
import PosNavIcon from './PosNavIcon.vue'
import { routeWithPosShell } from '../posShellQuery'
import { useAuthStore } from '../stores/auth'
import { useOrganizationStore } from '../stores/organization'
import { logout as logoutService } from '../services/auth.service'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const org = useOrganizationStore()

const MAIN_TAB_KEYS = ['pos', 'sales', 'products']

const userMenuOpen = ref(false)
const isLoading = ref(true)
/** Qarzdorlar / Boshqaruv — pastdagi strelka bilan ochiladi */
const extraNavOpen = ref(false)

const allTabs = computed(() => {
  const base = [
    { key: 'pos', to: routeWithPosShell('/app/pos'), label: 'Kassa', icon: 'pos' },
    { key: 'sales', to: routeWithPosShell('/app/sales'), label: 'Savdolar', icon: 'receipt' },
    { key: 'products', to: routeWithPosShell('/app/products'), label: 'Mahsulot', icon: 'box' },
    { key: 'debtors', to: routeWithPosShell('/app/debtors'), label: 'Qarzdorlar', icon: 'wallet' },
  ]
  if (auth.isAdmin) {
    base.push({
      key: 'admin',
      to: { name: 'dashboard' },
      label: 'Boshqaruv paneli',
      icon: 'admin',
    })
  }
  return base
})

const mainTabs = computed(() => allTabs.value.filter((t) => MAIN_TAB_KEYS.includes(t.key)))
const extraTabs = computed(() => allTabs.value.filter((t) => !MAIN_TAB_KEYS.includes(t.key)))

const extraNavActive = computed(() =>
  extraTabs.value.some((t) => {
    const path = typeof t.to === 'string' ? t.to : t.to?.path
    if (path && route.path === path) return true
    if (t.key === 'debtors' && route.path.startsWith('/app/debtors')) return true
    return false
  }),
)

watch(
  () => route.path,
  (path) => {
    if (
      path === '/app/pos' ||
      path.startsWith('/app/pos/') ||
      path === '/app/sales' ||
      path.startsWith('/app/sales/') ||
      path === '/app/products' ||
      path.startsWith('/app/products/')
    ) {
      extraNavOpen.value = false
    }
  },
)

function closeExtraNav() {
  extraNavOpen.value = false
}

function toggleExtraNav() {
  extraNavOpen.value = !extraNavOpen.value
}

onMounted(async () => {
  document.documentElement.classList.add('pos-shell-lock')
  try {
    const { bootAuthenticatedApp } = await import('../offline/sessionBootstrap')
    const result = await bootAuthenticatedApp(auth, org)
    if (!result.ok) {
      router.push('/auth/login')
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

onUnmounted(() => {
  document.documentElement.classList.remove('pos-shell-lock')
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
  <div class="pos-shell">
    <!-- ============ Sidebar (desktop) ============ -->
    <aside class="pos-side">
      <div class="pos-side__logo">
        <div class="pos-side__logo-wrap">
          <BrandLogo variant="sidebar-compact" />
          <ConnectivityStatusDot />
        </div>
      </div>

      <nav class="pos-side__nav">
        <RouterLink
          v-for="tab in mainTabs"
          :key="tab.key"
          :to="tab.to"
          class="pos-side__item"
          exact-active-class="is-active"
          @click="closeExtraNav"
        >
          <span class="pos-side__icon">
            <PosNavIcon :name="tab.icon" />
          </span>
          <span class="pos-side__label">{{ tab.label }}</span>
        </RouterLink>

        <template v-if="extraTabs.length">
          <button
            type="button"
            class="pos-side__item pos-side__item--toggle"
            :class="{ 'is-open': extraNavOpen, 'has-active-child': extraNavActive }"
            :aria-expanded="extraNavOpen"
            aria-label="Qo‘shimcha bo‘limlar"
            @click="toggleExtraNav"
          >
            <span class="pos-side__icon pos-side__icon--chevron">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </span>
            <span class="pos-side__label">Yana</span>
          </button>

          <Transition name="pos-extra">
            <div v-show="extraNavOpen" class="pos-side__extra">
              <RouterLink
                v-for="tab in extraTabs"
                :key="tab.key"
                :to="tab.to"
                class="pos-side__item pos-side__item--child"
                exact-active-class="is-active"
              >
                <span class="pos-side__icon">
                  <PosNavIcon :name="tab.icon" />
                </span>
                <span class="pos-side__label">{{ tab.label }}</span>
              </RouterLink>
            </div>
          </Transition>
        </template>
      </nav>

      <button
        type="button"
        class="pos-side__user"
        :aria-expanded="userMenuOpen"
        @click.stop="userMenuOpen = !userMenuOpen"
      >
        <span class="pos-side__avatar">{{ auth.initials || '?' }}</span>
      </button>
    </aside>

    <!-- ============ Main ============ -->
    <div class="pos-body">
      <main class="pos-content">
        <div v-if="isLoading" class="pos-loading">
          <div class="pos-spinner" />
          <span>Yuklanmoqda...</span>
        </div>
        <div v-else class="pos-content__view">
          <RouterView />
        </div>
      </main>
    </div>

    <!-- ============ Mobile bottom nav ============ -->
    <Transition name="pos-extra">
      <div v-if="extraNavOpen && extraTabs.length" class="pos-tabbar-extra">
        <RouterLink
          v-for="tab in extraTabs"
          :key="`ex-${tab.key}`"
          :to="tab.to"
          class="pos-tabbar-extra__item"
          exact-active-class="is-active"
          @click="extraNavOpen = false"
        >
          <PosNavIcon :name="tab.icon" />
          <span>{{ tab.label }}</span>
        </RouterLink>
      </div>
    </Transition>

    <nav
      class="pos-tabbar"
      :style="{ gridTemplateColumns: `repeat(${mainTabs.length + (extraTabs.length ? 1 : 0)}, minmax(0, 1fr))` }"
    >
      <RouterLink
        v-for="tab in mainTabs"
        :key="`m-${tab.key}`"
        :to="tab.to"
        class="pos-tab"
        exact-active-class="is-active"
        @click="closeExtraNav"
      >
        <span class="pos-tab__icon">
          <PosNavIcon :name="tab.icon" />
        </span>
        <span class="pos-tab__label">{{ tab.label }}</span>
      </RouterLink>
      <button
        v-if="extraTabs.length"
        type="button"
        class="pos-tab pos-tab--more"
        :class="{ 'is-open': extraNavOpen, 'is-active': extraNavActive }"
        :aria-expanded="extraNavOpen"
        aria-label="Yana"
        @click="toggleExtraNav"
      >
        <span class="pos-tab__icon pos-tab__icon--chevron">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9" />
          </svg>
        </span>
        <span class="pos-tab__label">Yana</span>
      </button>
    </nav>

    <!-- ============ User dropdown ============ -->
    <Transition name="pos-fade">
      <div v-if="userMenuOpen" class="pos-user-pop" @click.stop>
        <div class="pos-user-pop__head">
          <span class="pos-user-pop__avatar">{{ auth.initials || '?' }}</span>
          <div>
            <strong>{{ auth.fullName }}</strong>
            <small>Sotuvchi · {{ org.currentBranch?.name || '—' }}</small>
          </div>
        </div>
        <div v-if="org.branches.length > 1" class="pos-user-pop__branch">
          <label for="pos-branch-select">Filial</label>
          <select
            id="pos-branch-select"
            class="pos-user-pop__select"
            :value="org.currentBranchId || ''"
            @change="onBranchChange"
          >
            <option v-for="b in org.branches" :key="b.id" :value="b.id">
              {{ b.name }}
            </option>
          </select>
        </div>
        <button
          v-if="auth.isAdmin"
          type="button"
          class="pos-user-pop__logout"
          @click="
            userMenuOpen = false;
            router.push({ name: 'dashboard' })
          "
        >
          <svg
            viewBox="0 0 24 24"
            width="18"
            height="18"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M3 3h18v4H3z" />
            <path d="M5 7v14h14V7" />
          </svg>
          Admin bo‘limi
        </button>
        <button type="button" class="pos-user-pop__logout" @click="logout">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Tizimdan chiqish
        </button>
      </div>
    </Transition>

    <div v-if="userMenuOpen" class="pos-user-pop__backdrop" @click="userMenuOpen = false" />
  </div>
</template>

<style scoped>
.pos-shell {
  --pos-bg: #f1f5f9;
  --pos-side-bg: #ffffff;
  --pos-side-fg: #64748b;
  --pos-side-active: #0f172a;
  --pos-accent: #2563eb;
  --pos-card: #ffffff;
  --pos-line: #e2e8f0;
  --pos-text: #0f172a;
  --pos-muted: #64748b;

  display: grid;
  grid-template-columns: 84px 1fr;
  grid-template-rows: 1fr;
  height: 100vh;
  height: 100dvh;
  max-height: 100dvh;
  overflow: hidden;
  background: var(--pos-bg);
  color: var(--pos-text);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', sans-serif;
}

/* ============ Sidebar ============ */
.pos-side {
  background: var(--pos-side-bg);
  border-right: 1px solid var(--pos-line);
  box-shadow: 4px 0 24px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 18px 0;
  gap: 24px;
  position: sticky;
  top: 0;
  height: 100vh;
  height: 100dvh;
  max-height: 100dvh;
  overflow: hidden;
}

.pos-side__logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 0 4px;
}

.pos-side__logo-wrap {
  position: relative;
  display: inline-flex;
  max-width: 100%;
}

.pos-side__nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  align-items: center;
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: thin;
}

.pos-side__item {
  width: 68px;
  padding: 10px 0;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: var(--pos-side-fg);
  text-decoration: none;
  transition: all 0.15s ease;
  cursor: pointer;
}

.pos-side__item:hover {
  color: var(--pos-side-active);
  background: rgba(15, 23, 42, 0.06);
}

.pos-side__item.is-active {
  color: #fff;
  background: var(--pos-accent);
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.28);
}

.pos-side__icon {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
}

.pos-side__icon svg {
  width: 26px;
  height: 26px;
}

.pos-side__label {
  font-size: 0.7rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}

.pos-side__item--toggle {
  border: 0;
  background: transparent;
  font: inherit;
  width: 68px;
}

.pos-side__item--toggle .pos-side__icon--chevron svg {
  width: 22px;
  height: 22px;
  transition: transform 0.2s ease;
}

.pos-side__item--toggle.is-open .pos-side__icon--chevron svg {
  transform: rotate(180deg);
}

.pos-side__item--toggle.has-active-child:not(.is-open) {
  color: var(--pos-accent);
}

.pos-side__extra {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  align-items: center;
}

.pos-side__item--child {
  width: 64px;
  padding: 8px 0;
}

.pos-extra-enter-active,
.pos-extra-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
  overflow: hidden;
}

.pos-extra-enter-from,
.pos-extra-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.pos-side__user {
  background: transparent;
  border: 0;
  cursor: pointer;
  padding: 0;
}

.pos-side__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #334155;
  display: grid;
  place-items: center;
  font-weight: 600;
  font-size: 0.92rem;
  border: 2px solid #cbd5e1;
  transition: border-color 0.15s ease;
}

.pos-side__user:hover .pos-side__avatar {
  border-color: var(--pos-accent);
}

/* ============ Body ============ */
.pos-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

/* ============ Content ============ */
.pos-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 24px;
  background: var(--pos-bg);
}

.pos-content__view {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.pos-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px;
  gap: 14px;
  color: var(--pos-muted);
}

.pos-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid var(--pos-line);
  border-top-color: var(--pos-accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ============ User popup ============ */
.pos-user-pop {
  position: fixed;
  top: 16px;
  right: 16px;
  width: 280px;
  background: var(--pos-card);
  border: 1px solid var(--pos-line);
  border-radius: 14px;
  box-shadow: 0 16px 48px rgba(15, 23, 42, 0.12);
  z-index: 100;
  overflow: hidden;
}

.pos-user-pop__head {
  display: flex;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--pos-line);
  align-items: center;
}

.pos-user-pop__avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: var(--pos-accent);
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 600;
  flex-shrink: 0;
}

.pos-user-pop__head div {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.pos-user-pop__head strong {
  font-size: 0.96rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pos-user-pop__head small {
  font-size: 0.8rem;
  color: var(--pos-muted);
}

.pos-user-pop__branch {
  padding: 12px 16px;
  border-bottom: 1px solid var(--pos-line);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.pos-user-pop__branch label {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--pos-muted);
}

.pos-user-pop__select {
  width: 100%;
  border: 1px solid var(--pos-line);
  background: #f8fafc;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 0.92rem;
  outline: none;
  color: var(--pos-text);
}

.pos-user-pop__logout {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  background: transparent;
  border: 0;
  font-size: 0.95rem;
  font-weight: 500;
  color: #b91c1c;
  cursor: pointer;
  text-align: left;
  transition: background 0.15s ease;
}

.pos-user-pop__logout:hover {
  background: rgba(248, 113, 113, 0.12);
}

.pos-user-pop__backdrop {
  position: fixed;
  inset: 0;
  z-index: 99;
}

.pos-fade-enter-active,
.pos-fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.pos-fade-enter-from,
.pos-fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* ============ Mobile tabbar ============ */
.pos-tabbar {
  display: none;
}

/* ============ Responsive ============ */
@media (max-width: 880px) {
  .pos-shell {
    grid-template-columns: 1fr;
    height: 100dvh;
    max-height: 100dvh;
  }
  .pos-side {
    display: none;
  }
  .pos-content {
    padding: 14px;
    padding-bottom: 92px; /* tabbar */
    box-sizing: border-box;
  }
  .pos-tabbar-extra {
    position: fixed;
    bottom: calc(68px + env(safe-area-inset-bottom));
    left: 8px;
    right: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px;
    background: #fff;
    border: 1px solid var(--pos-line);
    border-radius: 14px;
    box-shadow: 0 -8px 32px rgba(15, 23, 42, 0.12);
    z-index: 21;
  }

  .pos-tabbar-extra__item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 10px;
    text-decoration: none;
    color: #334155;
    font-size: 0.95rem;
    font-weight: 500;
  }

  .pos-tabbar-extra__item :deep(svg) {
    width: 24px;
    height: 24px;
    flex-shrink: 0;
  }

  .pos-tabbar-extra__item.is-active {
    background: rgba(37, 99, 235, 0.1);
    color: var(--pos-accent);
  }

  .pos-tab {
    border: 0;
    background: transparent;
    font: inherit;
  }

  .pos-tab--more.is-open {
    color: var(--pos-accent);
  }

  .pos-tab__icon--chevron svg {
    width: 24px;
    height: 24px;
    transition: transform 0.2s ease;
  }

  .pos-tab--more.is-open .pos-tab__icon--chevron svg {
    transform: rotate(180deg);
  }

  .pos-tabbar {
    display: grid;
    /* Ustunlar soni :style bilan (tab lar soniga qarab) */
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: #ffffff;
    border-top: 1px solid var(--pos-line);
    z-index: 20;
    padding: 8px 0 calc(8px + env(safe-area-inset-bottom));
    box-shadow: 0 -4px 24px rgba(15, 23, 42, 0.08);
  }
  .pos-tab {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 6px 0;
    color: #94a3b8;
    text-decoration: none;
    min-height: 60px;
  }
  .pos-tab.is-active {
    color: var(--pos-accent);
  }
  .pos-tab.is-active .pos-tab__icon::after {
    content: '';
    position: absolute;
    bottom: -10px;
    width: 28px;
    height: 3px;
    border-radius: 3px;
    background: var(--pos-accent);
  }
  .pos-tab__icon {
    width: 28px;
    height: 28px;
    display: grid;
    place-items: center;
    position: relative;
  }
.pos-side__icon :deep(svg),
.pos-tab__icon :deep(svg) {
  width: 26px;
  height: 26px;
}
  .pos-tab__label {
    font-size: 0.72rem;
    font-weight: 500;
  }
  .pos-user-pop {
    top: 12px;
    right: 8px;
    left: 8px;
    width: auto;
  }
}
</style>

<style>
/* Kassa shell: butun sahifa emas, faqat ichki panellar scroll */
html.pos-shell-lock,
html.pos-shell-lock body {
  overflow: hidden;
  height: 100%;
}
</style>
