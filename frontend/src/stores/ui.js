import { defineStore } from 'pinia'

import api from '../services/api'

const LOCALE_KEY = 'savdopro_locale'
const THEME_KEY = 'savdopro_theme'

/** Qo‘llab-quvvatlanadigan UI tillari (faqat o‘zbek va rus). */
export const SUPPORTED_LOCALES = ['uz', 'ru']

export const LOCALE_LABELS = [
  { code: 'uz', label: 'UZB' },
  { code: 'ru', label: 'РУС' },
]

/** Eski `en` yoki noto‘g‘ri kodlarni joriy tilga normalizatsiya qiladi. */
export function normalizeLocale(code) {
  return code === 'ru' ? 'ru' : 'uz'
}

export const useUiStore = defineStore('ui', {
  state: () => {
    const stored = localStorage.getItem(LOCALE_KEY)
    return {
      locale: normalizeLocale(stored),
      theme: localStorage.getItem(THEME_KEY) || 'light',
    }
  },
  getters: {
    isDark: (state) => state.theme === 'dark',
  },
  actions: {
    applyTheme() {
      if (typeof document === 'undefined') return
      document.documentElement.setAttribute('data-theme', this.theme)
      document.documentElement.classList.toggle('theme-dark', this.theme === 'dark')
    },
    applyDocumentLang() {
      if (typeof document === 'undefined') return
      document.documentElement.lang = this.locale === 'ru' ? 'ru' : 'uz'
    },
    setTheme(theme) {
      this.theme = theme === 'dark' ? 'dark' : 'light'
      localStorage.setItem(THEME_KEY, this.theme)
      this.applyTheme()
    },
    toggleTheme() {
      this.setTheme(this.theme === 'dark' ? 'light' : 'dark')
    },
    async setLocale(code) {
      const locale = normalizeLocale(code)
      this.locale = locale
      localStorage.setItem(LOCALE_KEY, locale)
      this.applyDocumentLang()
      const token = localStorage.getItem('access_token')
      if (token) {
        try {
          await api.post('/auth/set-language/', { preferred_language: locale })
        } catch {
          /* mehmon yoki offline */
        }
      }
    },
    syncFromUser(user) {
      const lang = normalizeLocale(user?.preferred_language)
      if (lang !== this.locale) {
        this.locale = lang
        localStorage.setItem(LOCALE_KEY, lang)
        this.applyDocumentLang()
      }
    },
    init() {
      const locale = normalizeLocale(this.locale)
      if (locale !== this.locale) {
        this.locale = locale
        localStorage.setItem(LOCALE_KEY, locale)
      }
      this.applyTheme()
      this.applyDocumentLang()
    },
  },
})
