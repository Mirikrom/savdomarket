import { onMounted, onUnmounted } from 'vue'

/** Skaner aparat (klaviatura rejimi): tez belgilar + Enter. */
const SCAN_GAP_MS = 85
const MIN_CODE_LENGTH = 3

/**
 * @param {object} opts
 * @param {(code: string) => void} opts.onScan
 * @param {() => boolean} [opts.isActive] — false bo‘lsa tinglamaydi
 */
export function useHardwareBarcodeScanner({ onScan, isActive = () => true }) {
  let buffer = ''
  let lastKeyAt = 0
  let flushTimer = null

  function resetBuffer() {
    buffer = ''
    lastKeyAt = 0
    if (flushTimer) {
      clearTimeout(flushTimer)
      flushTimer = null
    }
  }

  function commit() {
    const code = buffer.trim()
    resetBuffer()
    if (code.length >= MIN_CODE_LENGTH) {
      onScan(code)
    }
  }

  function onKeydown(event) {
    if (!isActive()) return
    if (event.ctrlKey || event.metaKey || event.altKey) return

    const el = event.target
    const tag = el?.tagName
    const isEditable =
      tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el?.isContentEditable

    if (isEditable && !el?.dataset?.hardwareScan) {
      return
    }

    const now = Date.now()
    if (lastKeyAt && now - lastKeyAt > SCAN_GAP_MS) {
      buffer = ''
    }
    lastKeyAt = now

    if (event.key === 'Enter') {
      if (buffer.length >= MIN_CODE_LENGTH) {
        event.preventDefault()
        event.stopPropagation()
        commit()
      } else {
        resetBuffer()
      }
      return
    }

    if (event.key.length === 1) {
      buffer += event.key
      if (flushTimer) clearTimeout(flushTimer)
      flushTimer = setTimeout(resetBuffer, SCAN_GAP_MS + 60)
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', onKeydown, true)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', onKeydown, true)
    resetBuffer()
  })

  return { resetBuffer }
}
