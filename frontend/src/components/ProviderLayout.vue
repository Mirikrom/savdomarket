<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import AppPreferencesBar from './AppPreferencesBar.vue'
import BrandLogo from './BrandLogo.vue'
import { useI18n } from '../i18n'
import { useAuthStore } from '../stores/auth'
import { logout as logoutService } from '../services/auth.service'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const { tr } = useI18n()

function navActive(to) {
  if (to === '/provider') return route.path === '/provider' || route.path === '/provider/'
  return route.path === to || route.path.startsWith(`${to}/`)
}

const navOpen = ref(false)
const userMenuOpen = ref(false)
const isLoading = ref(true)

const navItems = computed(() => [
  { to: '/provider', label: tr('provider.nav.dashboard'), icon: 'dashboard' },
  { to: '/provider/orgs', label: tr('provider.nav.orgs'), icon: 'orgs' },
  { to: '/provider/plans', label: tr('provider.nav.plans'), icon: 'plan' },
  { to: '/provider/mijozlar', label: tr('provider.nav.clients'), icon: 'users' },
  { to: '/provider/settings', label: tr('provider.nav.settings'), icon: 'settings' },
])

const initials = computed(() => {
  const name = auth.user?.full_name || auth.user?.phone || 'SA'
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0])
    .join('')
    .toUpperCase()
})

async function ensureAuth() {
  if (!auth.loaded) {
    try {
      await auth.fetchMe()
    } catch {
      router.replace('/auth/login')
      return false
    }
  }
  if (!auth.isSuperuser) {
    router.replace('/app')
    return false
  }
  return true
}

onMounted(async () => {
  const ok = await ensureAuth()
  isLoading.value = !ok
  if (ok) isLoading.value = false
})

async function logout() {
  try {
    await logoutService()
  } catch {
    /* ignore */
  }
  auth.reset()
  router.replace('/auth/login')
}

function closeNav() {
  navOpen.value = false
}
</script>

<template>
  <div v-if="isLoading" class="prov-loading">
    <div class="prov-spinner" />
  </div>
  <div v-else class="prov-shell" :class="{ 'is-nav-open': navOpen }">
    <aside class="prov-sidebar">
      <div class="prov-brand">
        <BrandLogo variant="provider" />
        <div class="prov-brand__badge">Super Admin</div>
      </div>

      <nav class="prov-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="prov-nav__item"
          :class="{ 'is-active': navActive(item.to) }"
          @click="closeNav"
        >
          <span class="prov-nav__icon" :data-icon="item.icon">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <template v-if="item.icon === 'dashboard'">
                <rect x="3" y="3" width="7" height="9" /><rect x="14" y="3" width="7" height="5" /><rect x="14" y="12" width="7" height="9" /><rect x="3" y="16" width="7" height="5" />
              </template>
              <template v-else-if="item.icon === 'orgs'">
                <path d="M3 21h18" /><path d="M5 21V7l7-4 7 4v14" /><path d="M9 9h.01M9 13h.01M9 17h.01M15 9h.01M15 13h.01M15 17h.01" />
              </template>
              <template v-else-if="item.icon === 'plan'">
                <path d="M20 7H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2Z" /><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
              </template>
              <template v-else-if="item.icon === 'users'">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" />
              </template>
              <template v-else>
                <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
              </template>
            </svg>
          </span>
          <span class="prov-nav__label">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="prov-sidebar__footer">
        <button class="prov-back" @click="router.push({ name: 'provider-enter-store' })">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 18 9 12 15 6" />
          </svg>
          {{ tr('provider.backToApp') }}
        </button>
      </div>
    </aside>

    <div class="prov-main">
      <header class="prov-topbar">
        <button class="prov-burger" @click="navOpen = !navOpen" aria-label="Menyu">
          <span /><span /><span />
        </button>

        <div class="prov-topbar__brand">
          <span class="prov-topbar__title">{{ tr('provider.topbar.title') }}</span>
        </div>

        <div class="prov-topbar__actions">
          <AppPreferencesBar dark-surface />
          <div class="prov-user" @click.stop="userMenuOpen = !userMenuOpen">
          <div class="prov-user__avatar">{{ initials }}</div>
          <div class="prov-user__info">
            <div class="prov-user__name">{{ auth.user?.full_name || 'Provider' }}</div>
            <div class="prov-user__phone">{{ auth.user?.phone }}</div>
          </div>

          <div v-if="userMenuOpen" class="prov-user__menu" @click.stop>
            <button
              class="prov-user__menu-item"
              @click="router.push({ name: 'provider-enter-store' })"
            >
              {{ tr('provider.user.toApp') }}
            </button>
            <button class="prov-user__menu-item is-danger" @click="logout">
              {{ tr('provider.user.logout') }}
            </button>
          </div>
        </div>
        </div>
      </header>

      <main class="prov-content">
        <RouterView />
      </main>
    </div>

    <div v-if="navOpen" class="prov-backdrop" @click="navOpen = false" />
  </div>
</template>

<style scoped>
.prov-loading {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #0b1220;
}
.prov-spinner {
  width: 42px;
  height: 42px;
  border: 3px solid rgba(255, 255, 255, 0.12);
  border-top-color: #f97316;
  border-radius: 50%;
  animation: prov-spin 0.9s linear infinite;
}
@keyframes prov-spin {
  to { transform: rotate(360deg); }
}

.prov-shell {
  display: grid;
  grid-template-columns: 260px 1fr;
  min-height: 100vh;
  background: #0b1220;
  color: #e5e7eb;
}

/* Sidebar */
.prov-sidebar {
  background: #0f172a;
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  padding: 20px 14px;
  position: sticky;
  top: 0;
  height: 100vh;
}
.prov-brand {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
  padding: 4px 8px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 16px;
}
.prov-brand__badge {
  font-size: 11px;
  color: #fb923c;
  text-transform: uppercase;
  letter-spacing: 0.7px;
  font-weight: 600;
}

.prov-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.prov-nav__item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 12px;
  border-radius: 10px;
  color: #cbd5e1;
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.15s, color 0.15s;
}
.prov-nav__item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: #fff;
}
.prov-nav__item.is-active {
  background: rgba(249, 115, 22, 0.12);
  color: #fb923c;
}
.prov-nav__icon {
  width: 22px;
  display: grid;
  place-items: center;
  opacity: 0.85;
}
.prov-nav__item.is-active .prov-nav__icon {
  opacity: 1;
}

.prov-sidebar__footer {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  padding-top: 12px;
}
.prov-back {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  background: transparent;
  color: #94a3b8;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}
.prov-back:hover {
  background: rgba(255, 255, 255, 0.04);
  color: #fff;
}

/* Topbar */
.prov-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.prov-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  background: #0f172a;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  position: sticky;
  top: 0;
  z-index: 10;
}
.prov-topbar__brand {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
  justify-content: center;
}
.prov-topbar__title {
  font-weight: 600;
  font-size: 15px;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.prov-topbar__actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.prov-burger {
  display: none;
  flex-direction: column;
  gap: 4px;
  width: 38px;
  height: 38px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  justify-content: center;
  align-items: center;
  cursor: pointer;
}
.prov-burger span {
  width: 18px;
  height: 2px;
  background: #cbd5e1;
  border-radius: 2px;
}

.prov-user {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  position: relative;
  padding: 6px 10px;
  border-radius: 10px;
}
.prov-user:hover {
  background: rgba(255, 255, 255, 0.04);
}
.prov-user__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f97316, #ef4444);
  color: #fff;
  display: grid;
  place-items: center;
  font-weight: 700;
  font-size: 13px;
}
.prov-user__name {
  font-size: 13px;
  font-weight: 600;
  color: #fff;
}
.prov-user__phone {
  font-size: 11px;
  color: #94a3b8;
}
.prov-user__menu {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  min-width: 200px;
  padding: 6px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
}
.prov-user__menu-item {
  width: 100%;
  text-align: left;
  background: transparent;
  border: 0;
  color: #e5e7eb;
  padding: 9px 10px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.prov-user__menu-item:hover {
  background: rgba(255, 255, 255, 0.06);
}
.prov-user__menu-item.is-danger {
  color: #fca5a5;
}

.prov-content {
  flex: 1;
  padding: 24px;
  background: #0b1220;
  overflow-x: hidden;
}

.prov-backdrop {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  z-index: 20;
}

/* Mobile */
@media (max-width: 900px) {
  .prov-shell {
    grid-template-columns: 1fr;
  }
  .prov-sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    left: -280px;
    width: 260px;
    z-index: 30;
    transition: left 0.22s ease;
  }
  .prov-shell.is-nav-open .prov-sidebar {
    left: 0;
  }
  .prov-shell.is-nav-open .prov-backdrop {
    display: block;
  }
  .prov-burger {
    display: flex;
  }
  .prov-user__info {
    display: none;
  }
  .prov-content {
    padding: 16px;
  }
}
</style>
