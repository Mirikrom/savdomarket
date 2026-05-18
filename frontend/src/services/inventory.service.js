import api from './api'

export const stockMovements = {
  list: (params = {}) =>
    api.get('/stock-movements/', { params }).then((r) => r.data.results || r.data),
  create: (payload) => api.post('/stock-movements/', payload).then((r) => r.data),
  bulkIn: (payload) => api.post('/stock-movements/bulk-in/', payload).then((r) => r.data),
}

export const productBatches = {
  list: (params = {}) =>
    api.get('/product-batches/', { params }).then((r) => r.data.results || r.data),
  create: (payload) => api.post('/product-batches/', payload).then((r) => r.data),
  update: (id, payload) => api.patch(`/product-batches/${id}/`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/product-batches/${id}/`).then((r) => r.data),
}

export const stockLevels = {
  list: (params = {}) => api.get('/stock-levels/', { params }).then((r) => r.data),
}
