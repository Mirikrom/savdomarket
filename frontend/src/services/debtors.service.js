import api from './api'

export const debtors = {
  list: (params = {}) =>
    api.get('/debtors/', { params }).then((r) => r.data.results || r.data),
  retrieve: (id) => api.get(`/debtors/${id}/`).then((r) => r.data),
  create: (payload) => api.post('/debtors/', payload).then((r) => r.data),
  update: (id, payload) => api.patch(`/debtors/${id}/`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/debtors/${id}/`),
  pay: (id, payload) => api.post(`/debtors/${id}/pay/`, payload).then((r) => r.data),
}
