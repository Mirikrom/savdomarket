<script setup>
import { ref } from 'vue'

defineProps({
  open: { type: Boolean, required: true },
  title: { type: String, default: '' },
  width: { type: String, default: '480px' },
})

const emit = defineEmits(['close'])

/** Tashqi fonni bosish bilan yopish — faqat bosish va qo‘yish ikkalasi ham fon ustida bo‘lsa (modal ichidan sudrab chiqib qo‘yishda yopilmasin). */
const backdropPointerDown = ref(false)

function isPrimaryButton(e) {
  return e.button === 0
}

function onBackdropPointerDown(e) {
  if (!isPrimaryButton(e)) return
  backdropPointerDown.value = e.target === e.currentTarget
}

function onBackdropPointerUp(e) {
  if (!isPrimaryButton(e)) return
  if (backdropPointerDown.value && e.target === e.currentTarget) {
    emit('close')
  }
  backdropPointerDown.value = false
}

function onBackdropPointerLeave() {
  backdropPointerDown.value = false
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="open"
        class="modal-backdrop"
        @pointerdown="onBackdropPointerDown"
        @pointerup="onBackdropPointerUp"
        @pointerleave="onBackdropPointerLeave"
      >
        <div class="modal-card" :style="{ '--modal-max-width': width }" @click.stop>
          <header class="modal-card__head">
            <h3>{{ title }}</h3>
            <button class="modal-close" type="button" aria-label="Yopish" @click="emit('close')">
              ×
            </button>
          </header>
          <div class="modal-card__body">
            <slot />
          </div>
          <footer v-if="$slots.footer" class="modal-card__foot">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
