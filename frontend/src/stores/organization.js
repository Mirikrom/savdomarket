import { defineStore } from 'pinia'

import api from '../services/api'

const BRANCH_KEY = 'current_branch_id'

export const useOrganizationStore = defineStore('organization', {
  state: () => ({
    organization: null,
    branches: [],
    currentBranchId: Number(localStorage.getItem(BRANCH_KEY)) || null,
    plan: null,
    subscription: null,
    loading: false,
  }),
  getters: {
    currentBranch: (state) =>
      state.branches.find((b) => b.id === state.currentBranchId) || state.branches[0] || null,
    isProPlan: (state) => state.plan?.code === 'pro',
    hasFeature: (state) => (code) => {
      if (!state.plan) return false
      if (state.plan.code === 'pro') return true
      return !!state.plan.feature_flags?.[code]
    },
  },
  actions: {
    async loadAll() {
      this.loading = true
      try {
        await Promise.all([this.fetchOrganization(), this.fetchBranches(), this.fetchCurrentPlan()])
        if (this.organization?.id && this.currentBranchId) {
          const { scheduleFullSync } = await import('../offline/syncScheduler')
          const { saveOrganizationSnapshot } = await import('../offline/posContext')
          await saveOrganizationSnapshot(this).catch(() => {})
          await scheduleFullSync(this.organization.id, this.currentBranchId, {
            branches: this.branches,
            organization: this.organization,
            force: true,
          }).catch(() => {})
        }
      } catch {
        const { hydrateOrganizationStore } = await import('../offline/posContext')
        await hydrateOrganizationStore(this)
      } finally {
        const { hydrateOrganizationStore } = await import('../offline/posContext')
        await hydrateOrganizationStore(this)
        this.loading = false
      }
    },

    async fetchOrganization() {
      const { data } = await api.get('/organizations/')
      const list = data.results || data
      this.organization = list[0] || null
    },

    async fetchBranches() {
      const { data } = await api.get('/branches/')
      const list = data.results || data
      this.branches = list
      if (!this.currentBranchId && list.length) {
        this.setCurrentBranch(list.find((b) => b.is_main)?.id || list[0].id)
      }
    },

    async fetchCurrentPlan() {
      try {
        const { data } = await api.get('/subscriptions/current/')
        this.subscription = data.subscription || null
        this.plan = data.subscription?.plan_detail || null
      } catch {
        this.subscription = null
        this.plan = null
      }
    },

    async setCurrentBranch(branchId) {
      this.currentBranchId = branchId
      if (branchId) localStorage.setItem(BRANCH_KEY, String(branchId))
      else localStorage.removeItem(BRANCH_KEY)
      if (this.organization?.id && branchId) {
        const { scheduleFullSync } = await import('../offline/syncScheduler')
        scheduleFullSync(this.organization.id, branchId, {
          branches: this.branches,
          organization: this.organization,
          force: true,
        }).catch(() => {})
      }
    },

    reset() {
      this.organization = null
      this.branches = []
      this.currentBranchId = null
      this.plan = null
      this.subscription = null
      localStorage.removeItem(BRANCH_KEY)
    },
  },
})
