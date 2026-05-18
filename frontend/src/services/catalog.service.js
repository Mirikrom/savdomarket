import api from './api'

function appendProductFormData(formData, payload) {
  for (const [key, value] of Object.entries(payload)) {
    if (value === null || value === undefined) continue
    formData.append(key, String(value))
  }
}

export const categories = {
  list: () => api.get('/categories/').then((r) => r.data.results || r.data),
  create: (payload) => api.post('/categories/', payload).then((r) => r.data),
  update: (id, payload) => api.patch(`/categories/${id}/`, payload).then((r) => r.data),
  remove: (id) => api.delete(`/categories/${id}/`).then((r) => r.data),
}

export const products = {
  list: (params = {}) =>
    api.get('/products/', { params }).then((r) => r.data.results || r.data),
  retrieve: (id) => api.get(`/products/${id}/`).then((r) => r.data),
  create: (payload, options = {}) => {
    const { image } = options
    if (image instanceof File) {
      const fd = new FormData()
      appendProductFormData(fd, payload)
      fd.append('image', image)
      return api.post('/products/', fd).then((r) => r.data)
    }
    return api.post('/products/', payload).then((r) => r.data)
  },
  update: (id, payload, options = {}) => {
    const { image, clearImage } = options
    if (image instanceof File || clearImage) {
      const fd = new FormData()
      appendProductFormData(fd, payload)
      if (image instanceof File) fd.append('image', image)
      if (clearImage) fd.append('clear_image', 'true')
      return api.patch(`/products/${id}/`, fd).then((r) => r.data)
    }
    return api.patch(`/products/${id}/`, payload).then((r) => r.data)
  },
  remove: (id) => api.delete(`/products/${id}/`).then((r) => r.data),
}
