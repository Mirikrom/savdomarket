import { computed, toRef } from 'vue'

import { messages } from './messages'
import { useUiStore } from '../stores/ui'

/** Raqam/sana formati uchun Intl locale (faqat uz / ru). */
export function numberLocaleForUi(locale) {
  return locale === 'ru' ? 'ru-RU' : 'uz-UZ'
}

/** String.localeCompare uchun (faqat uz / ru). */
export function collatorLocaleForUi(locale) {
  return locale === 'ru' ? 'ru' : 'uz'
}

export function translate(locale, key, params = {}) {
  const loc = locale === 'ru' ? 'ru' : 'uz'
  const dict = messages[loc] || messages.uz
  let text = dict[key] ?? messages.uz[key] ?? messages.ru[key] ?? key
  for (const [k, v] of Object.entries(params)) {
    text = text.replace(`{${k}}`, String(v))
  }
  return text
}

/** Ro‘yxatdan kelgan standart asosiy filial nomini joriy tilga moslashtiradi. */
const MAIN_BRANCH_DEFAULT_NAMES = new Set(['Asosiy filial', 'Main Branch'])

export function branchDisplayName(locale, branch) {
  if (!branch?.name) return '—'
  const n = String(branch.name).trim()
  if (branch.is_main && MAIN_BRANCH_DEFAULT_NAMES.has(n)) {
    return translate(locale, 'branch.defaultMain')
  }
  return branch.name
}

/** Jadval/API dan kelgan filial nomini joriy tilga moslashtiradi. */
export function resolveBranchName(locale, branches, name) {
  if (!name) return '—'
  const list = branches || []
  const found = list.find((b) => b.name === name)
  if (found) return branchDisplayName(locale, found)
  const n = String(name).trim()
  if (MAIN_BRANCH_DEFAULT_NAMES.has(n)) {
    return translate(locale, 'branch.defaultMain')
  }
  return name
}

/** Reaktiv matnlar: useT({ title: 'auth.login.title' }) */
export function useT(keyMap) {
  const ui = useUiStore()
  const out = {}
  for (const [name, key] of Object.entries(keyMap)) {
    if (typeof key === 'string') {
      out[name] = computed(() => translate(ui.locale, key))
    }
  }
  return out
}

/** Parametrli: useTParam('auth.register.otpHint', () => ({ phone: masked })) */
export function useTParam(key, paramsFn) {
  const ui = useUiStore()
  return computed(() => translate(ui.locale, key, paramsFn()))
}

/**
 * `tr()` har safar `useUiStore().locale` ni o‘qiydi — boshqa `computed` ichida chaqirilganda
 * ham Vue/Pinia reaktiv bog‘lanish ishlaydi (`storeToRefs` + closure ba’zan yo‘qolardi).
 */
export function useI18n() {
  const ui = useUiStore()
  const locale = toRef(ui, 'locale')

  function tr(key, params = {}) {
    return translate(ui.locale, key, params)
  }

  function branchLabel(branch) {
    return branchDisplayName(ui.locale, branch)
  }

  function branchName(name, branches) {
    return resolveBranchName(ui.locale, branches, name)
  }

  return { ui, tr, locale, branchLabel, branchName }
}
