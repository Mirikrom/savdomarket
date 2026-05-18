import api from './api'

export const users = {
  list: () => api.get('/accounts/users/').then((r) => r.data.results || r.data),
}

export const roles = {
  list: () => api.get('/accounts/roles/').then((r) => r.data.results || r.data),
}

export const organizationUsers = {
  list: () => api.get('/accounts/organization-users/').then((r) => r.data.results || r.data),
  create: (payload) => api.post('/accounts/organization-users/', payload).then((r) => r.data),
  update: (id, payload) =>
    api.patch(`/accounts/organization-users/${id}/`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/accounts/organization-users/${id}/`).then((r) => r.data),
  invite: (payload) =>
    api.post('/accounts/organization-users/invite/', payload).then((r) => r.data),
}

export const sessions = {
  list: () => api.get('/accounts/sessions/').then((r) => r.data.results || r.data),
  revoke: (id) => api.post(`/auth/sessions/${id}/revoke/`).then((r) => r.data),
}
