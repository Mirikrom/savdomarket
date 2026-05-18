import { liveQuery } from 'dexie'
import { onScopeDispose, ref, watchEffect } from 'vue'

/**
 * Dexie liveQuery uchun Vue 3 composable (dexie-vue-addons npm da yo‘q).
 */
export function useDexieLiveQuery(querier, { initialValue = undefined } = {}) {
  const data = ref(initialValue)
  let subscription

  watchEffect((onInvalidate) => {
    subscription?.unsubscribe()
    const observable = liveQuery(querier)
    subscription = observable.subscribe({
      next: (value) => {
        data.value = value
      },
    })
    onInvalidate(() => subscription?.unsubscribe())
  })

  onScopeDispose(() => subscription?.unsubscribe())

  return data
}
