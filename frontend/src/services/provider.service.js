import api from './api'

const cfg = { headers: { 'X-Skip-Org': '1' } }

export const providerService = {
  stats: () => api.get('/provider/stats/', cfg).then((r) => r.data),

  changePassword: (payload) =>
    api.post('/provider/change-password/', payload, cfg).then((r) => r.data),

  plans: {
    list: () => api.get('/provider/plans/', cfg).then((r) => r.data.results || r.data),
    retrieve: (id) => api.get(`/provider/plans/${id}/`, cfg).then((r) => r.data),
    patch: (id, payload) =>
      api.patch(`/provider/plans/${id}/`, payload, cfg).then((r) => r.data),
  },

  users: {
    list: (params = {}) =>
      api.get('/provider/users/', { ...cfg, params }).then((r) => r.data),
    retrieve: (id) => api.get(`/provider/users/${id}/`, cfg).then((r) => r.data),
    /** Yangi do'kon + owner login + parol (mijozga berish) */
    bootstrapClient: (payload) =>
      api.post('/provider/users/bootstrap-client/', payload, cfg).then((r) => r.data),
    unlock: (id) =>
      api.post(`/provider/users/${id}/unlock/`, {}, cfg).then((r) => r.data),
    setActive: (id, isActive) =>
      api.post(`/provider/users/${id}/set-active/`, { is_active: isActive }, cfg).then((r) => r.data),
  },

  orgs: {
    list: (params = {}) =>
      api.get('/provider/organizations/', { ...cfg, params }).then((r) => r.data.results || r.data),
    retrieve: (id) =>
      api.get(`/provider/organizations/${id}/`, cfg).then((r) => r.data),
    create: (payload) =>
      api.post('/provider/organizations/', payload, cfg).then((r) => r.data),
    patch: (id, payload) =>
      api.patch(`/provider/organizations/${id}/`, payload, cfg).then((r) => r.data),
    delete: (id) => api.delete(`/provider/organizations/${id}/`, cfg).then((r) => r.data),
    suspend: (id) =>
      api.post(`/provider/organizations/${id}/suspend/`, {}, cfg).then((r) => r.data),
    activate: (id) =>
      api.post(`/provider/organizations/${id}/activate/`, {}, cfg).then((r) => r.data),
    extendTrial: (id, days = 30) =>
      api.post(`/provider/organizations/${id}/extend-trial/`, { days }, cfg).then((r) => r.data),
    changePlan: (id, planCode, days = 30) =>
      api
        .post(
          `/provider/organizations/${id}/change-plan/`,
          { plan_code: planCode, days },
          cfg,
        )
        .then((r) => r.data),
    setRemainingDays: (id, days = 0) =>
      api
        .post(`/provider/organizations/${id}/set-remaining-days/`, { days }, cfg)
        .then((r) => r.data),
    impersonate: (id) =>
      api.post(`/provider/organizations/${id}/impersonate/`, {}, cfg).then((r) => r.data),
    staffRoles: (id) =>
      api.get(`/provider/organizations/${id}/staff-roles/`, cfg).then((r) => r.data),
    inviteStaff: (id, payload) =>
      api.post(`/provider/organizations/${id}/invite-staff/`, payload, cfg).then((r) => r.data),
  },
}

export default providerService
