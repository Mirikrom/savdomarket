import { onMounted, onUnmounted, ref } from 'vue'

/** Telefon/planshet tor ekran (global mobil breakpoint bilan bir xil). */
export const MOBILE_MEDIA_QUERY = '(max-width: 640px)'

export function useIsMobileViewport() {
  const isMobile = ref(false)
  let mql = null

  function update() {
    isMobile.value = typeof window !== 'undefined' && window.matchMedia(MOBILE_MEDIA_QUERY).matches
  }

  onMounted(() => {
    mql = window.matchMedia(MOBILE_MEDIA_QUERY)
    update()
    mql.addEventListener('change', update)
  })

  onUnmounted(() => {
    mql?.removeEventListener('change', update)
  })

  return { isMobile }
}
