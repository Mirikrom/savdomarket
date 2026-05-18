import api from './api'

export const plans = {
  list: () => api.get('/plans/').then((r) => r.data.results || r.data),
}

export const subscriptions = {
  current: () => api.get('/subscriptions/current/').then((r) => r.data),
  list: () => api.get('/subscriptions/').then((r) => r.data.results || r.data),
  invoices: () =>
    api.get('/subscription-invoices/').then((r) => r.data.results || r.data),
}
