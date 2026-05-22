<script setup>
import { storeToRefs } from 'pinia'

import { useI18n } from '../i18n'
import { useNotifyStore } from '../stores/notify'

const notify = useNotifyStore()
const { open, title, message, variant } = storeToRefs(notify)
const { tr } = useI18n()

function onKeydown(e) {
  if (e.key === 'Escape' && open.value) notify.close()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="notify-fade">
      <div
        v-if="open"
        class="notify-backdrop"
        role="presentation"
        @click="notify.close"
      />
    </Transition>
    <Transition name="notify-pop">
      <div
        v-if="open"
        class="notify-dialog"
        role="alertdialog"
        :aria-labelledby="title ? 'notify-title' : undefined"
        aria-describedby="notify-message"
        @keydown="onKeydown"
      >
        <div class="notify-dialog__icon" :class="`notify-dialog__icon--${variant}`" aria-hidden="true">
          <svg v-if="variant === 'warning'" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 9v4M12 17h.01" stroke-linecap="round" />
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          </svg>
          <svg v-else viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" stroke-linecap="round" />
          </svg>
        </div>
        <h3 v-if="title" id="notify-title" class="notify-dialog__title">{{ title }}</h3>
        <p id="notify-message" class="notify-dialog__message">{{ message }}</p>
        <button type="button" class="btn btn--primary notify-dialog__btn" @click="notify.close">
          {{ tr('errors.ok') }}
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.notify-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(2px);
}

.notify-dialog {
  position: fixed;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 1201;
  width: min(400px, calc(100vw - 32px));
  padding: 24px 22px 20px;
  background: var(--surface, #fff);
  border: 1px solid var(--line, #e2e8f0);
  border-radius: 16px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
  text-align: center;
}

.notify-dialog__icon {
  width: 52px;
  height: 52px;
  margin: 0 auto 14px;
  border-radius: 50%;
  display: grid;
  place-items: center;
}

.notify-dialog__icon--warning {
  background: rgba(245, 158, 11, 0.15);
  color: #d97706;
}

.notify-dialog__icon--error {
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
}

.notify-dialog__icon--info {
  background: rgba(37, 99, 235, 0.12);
  color: #2563eb;
}

.notify-dialog__title {
  margin: 0 0 8px;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text, #0f172a);
}

.notify-dialog__message {
  margin: 0 0 20px;
  font-size: 0.95rem;
  line-height: 1.5;
  color: var(--muted, #64748b);
}

.notify-dialog__btn {
  min-width: 120px;
}

.notify-fade-enter-active,
.notify-fade-leave-active {
  transition: opacity 0.2s ease;
}

.notify-fade-enter-from,
.notify-fade-leave-to {
  opacity: 0;
}

.notify-pop-enter-active,
.notify-pop-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.notify-pop-enter-from,
.notify-pop-leave-to {
  opacity: 0;
  transform: translate(-50%, -48%) scale(0.96);
}

[data-theme='dark'] .notify-dialog {
  background: #1e293b;
  border-color: #334155;
}

[data-theme='dark'] .notify-dialog__title {
  color: #f1f5f9;
}

[data-theme='dark'] .notify-dialog__message {
  color: #94a3b8;
}
</style>
