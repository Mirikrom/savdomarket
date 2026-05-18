import api from './api'

export const organizations = {
  list: () => api.get('/organizations/').then((r) => r.data.results || r.data),
  retrieve: (id) => api.get(`/organizations/${id}/`).then((r) => r.data),
}

export const branches = {
  list: () => api.get('/branches/').then((r) => r.data.results || r.data),
  create: (payload) => api.post('/branches/', payload).then((r) => r.data),
  update: (id, payload) => api.patch(`/branches/${id}/`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/branches/${id}/`).then((r) => r.data),
}
