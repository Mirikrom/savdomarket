<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { translate } from '../i18n'
import { LOCALE_LABELS, useUiStore } from '../stores/ui'

defineProps({
  /** Login / register: o‘ng yuqori burchak */
  floating: { type: Boolean, default: false },
  /** Provider, POS: qorong‘i fon ustida */
  darkSurface: { type: Boolean, default: false },
})

const ui = useUiStore()
const { locale, isDark } = storeToRefs(ui)
const langOpen = ref(false)
const dropdownRef = ref(null)

const themeLabel = computed(() =>
  translate(locale.value, isDark.value ? 'prefs.theme.light' : 'prefs.theme.dark'),
)

const langMenuAria = computed(() => translate(locale.value, 'prefs.langMenu'))

const currentLabel = computed(() => {
  const item = LOCALE_LABELS.find((l) => l.code === locale.value)
  return item?.label ?? 'UZB'
})

function toggleLangMenu() {
  langOpen.value = !langOpen.value
}

async function pickLocale(code) {
  await ui.setLocale(code)
  langOpen.value = false
}

function onDocPointerDown(e) {
  if (!langOpen.value) return
  const root = dropdownRef.value
  if (root && !root.contains(e.target)) {
    langOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('pointerdown', onDocPointerDown, true)
})

onUnmounted(() => {
  document.removeEventListener('pointerdown', onDocPointerDown, true)
})
</script>

<template>
  <div
    class="app-prefs"
    :class="{ 'app-prefs--floating': floating, 'app-prefs--on-dark': darkSurface }"
    role="toolbar"
  >
    <div ref="dropdownRef" class="app-prefs__lang-dropdown">
      <button
        type="button"
        class="app-prefs__lang-trigger"
        :class="{ 'is-open': langOpen }"
        :aria-expanded="langOpen"
        aria-haspopup="listbox"
        aria-controls="app-prefs-lang-list"
        @click.stop="toggleLangMenu"
      >
        <span class="app-prefs__lang-trigger-label">{{ currentLabel }}</span>
        <span class="app-prefs__lang-chevron" aria-hidden="true" />
      </button>

      <div
        id="app-prefs-lang-panel"
        class="app-prefs__lang-panel"
        :class="{ 'is-open': langOpen }"
      >
        <ul
          id="app-prefs-lang-list"
          class="app-prefs__lang-list"
          role="listbox"
          :aria-label="langMenuAria"
        >
          <li v-for="item in LOCALE_LABELS" :key="item.code" role="none">
            <button
              type="button"
              role="option"
              class="app-prefs__lang-option"
              :class="{ 'is-current': locale === item.code }"
              :aria-selected="locale === item.code"
              @click.stop="pickLocale(item.code)"
            >
              {{ item.label }}
            </button>
          </li>
        </ul>
      </div>
    </div>

    <button
      type="button"
      class="app-prefs__theme"
      :title="themeLabel"
      :aria-label="themeLabel"
      @click.stop="ui.toggleTheme()"
    >
      <span v-if="isDark" class="app-prefs__icon" aria-hidden="true">☀️</span>
      <span v-else class="app-prefs__icon" aria-hidden="true">🌙</span>
    </button>
  </div>
</template>
