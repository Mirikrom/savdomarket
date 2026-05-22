import { useI18n } from '../i18n'
import { useNotifyStore } from '../stores/notify'
import { resolveApiError } from '../utils/apiErrors'

/** `alert()` o‘rniga — API xatolarini o‘zbekcha modalda ko‘rsatish. */
export function useApiNotify() {
  const notify = useNotifyStore()
  const { tr } = useI18n()

  function showApiError(error, fallbackKey = 'errors.generic') {
    if (error?._notifyHandled) return
    notify.showApiError(error, fallbackKey)
  }

  function showMessage(message, title) {
    notify.showError(message, title)
  }

  function resolveMessage(error, fallbackKey = 'errors.generic') {
    return resolveApiError(error, tr, tr(fallbackKey))
  }

  return { notify, showApiError, showMessage, resolveMessage }
}
