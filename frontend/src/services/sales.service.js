import api from './api'

export const sales = {
  list: (params = {}) => api.get('/sales/', { params }).then((r) => r.data.results || r.data),
  retrieve: (id) => api.get(`/sales/${id}/`).then((r) => r.data),
  create: (payload) => api.post('/sales/', payload).then((r) => r.data),
  todaySummary: (params = {}) =>
    api.get('/sales/today-summary/', { params }).then((r) => r.data),
}
