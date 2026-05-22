import { defineStore } from 'pinia'

import { translate } from '../i18n'
import { resolveApiError } from '../utils/apiErrors'
import { useUiStore } from './ui'

function tr(key, params = {}) {
  const ui = useUiStore()
  return translate(ui.locale, key, params)
}

export const useNotifyStore = defineStore('notify', {
  state: () => ({
    open: false,
    title: '',
    message: '',
    /** info | warning | error */
    variant: 'info',
  }),
  actions: {
    show({ title, message, variant = 'info' }) {
      this.title = title || ''
      this.message = message || ''
      this.variant = variant
      this.open = true
    },
    showError(message, title) {
      this.show({
        title: title || tr('errors.title'),
        message: message || tr('errors.generic'),
        variant: 'error',
      })
    },
    showWarning(message, title) {
      this.show({
        title: title || tr('errors.title'),
        message,
        variant: 'warning',
      })
    },
    showApiError(error, fallbackKey = 'errors.generic') {
      const msg = resolveApiError(error, tr, tr(fallbackKey))
      const variant = error?.response?.status === 403 ? 'warning' : 'error'
      this.show({
        title: tr('errors.title'),
        message: msg,
        variant,
      })
    },
    close() {
      this.open = false
    },
  },
})
