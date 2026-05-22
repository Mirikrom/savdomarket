import { defineStore } from 'pinia'

import api from '../services/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    organizationId: null,
    role: null,
    branchId: null,
    memberships: [],
    loaded: false,
    loading: false,
    error: null,
  }),
  getters: {
    isAuthenticated: () => !!localStorage.getItem('access_token'),
    isSuperuser: (state) => !!state.user?.is_superuser,
    isProviderAdmin: (state) => !!state.user?.is_superuser,
    isOwner: (state) => state.role === 'owner',
    /** Do‘kon egasi — to‘liq admin panel */
    isAdmin: (state) => state.role === 'owner',
    /** Sotuvchi — kassa, mahsulot, kirim */
    isSeller: (state) => state.role === 'seller',
    /** @deprecated isSeller ishlating */
    isCashier: (state) => state.role === 'seller',
    fullName: (state) => state.user?.full_name || state.user?.phone || '',
    initials: (state) => {
      const name = state.user?.full_name || state.user?.phone || ''
      return name
        .split(/\s+/)
        .filter(Boolean)
        .slice(0, 2)
        .map((s) => s[0])
        .join('')
        .toUpperCase()
    },
  },
  actions: {
    async fetchMe() {
      this.loading = true
      this.error = null
      try {
        const { data } = await api.get('/accounts/me/')
        this.user = data.user
        this.organizationId = data.organization_id
        this.role = data.role
        this.branchId = data.branch_id
        this.memberships = data.memberships || []
        if (this.organizationId) {
          localStorage.setItem('organization_id', String(this.organizationId))
        } else {
          localStorage.removeItem('organization_id')
        }
        if (this.role) {
          localStorage.setItem('user_role', this.role)
        } else {
          localStorage.removeItem('user_role')
        }
        if (this.user?.is_superuser) {
          localStorage.setItem('is_provider', '1')
        } else {
          localStorage.removeItem('is_provider')
        }
        const displayName =
          this.user?.full_name || this.user?.phone || this.user?.username || ''
        if (displayName) {
          localStorage.setItem('cashier_display_name', displayName)
        }
        this.loaded = true
      } catch (err) {
        this.error = err
        throw err
      } finally {
        this.loading = false
      }
    },

    setCurrentOrganization(orgId) {
      this.organizationId = orgId
      if (orgId) localStorage.setItem('organization_id', String(orgId))
      else localStorage.removeItem('organization_id')
    },

    reset() {
      this.user = null
      this.organizationId = null
      this.role = null
      this.branchId = null
      this.memberships = []
      this.loaded = false
      this.error = null
      localStorage.removeItem('organization_id')
      localStorage.removeItem('user_role')
      localStorage.removeItem('is_provider')
      localStorage.removeItem('cashier_display_name')
    },
  },
})
