<script setup>
import { computed } from 'vue'

import { useI18n } from '../i18n'

const props = defineProps({
  columns: { type: Array, required: true }, // [{key, label, formatter?, width?}]
  rows: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  rowKey: { type: String, default: 'id' },
  emptyText: { type: String, default: 'Ma\u2019lumot topilmadi.' },
  /** Amallar ustuni sarlavhasi (null — `table.actions` kaliti). */
  actionsLabel: { type: String, default: null },
  /** Yuklash qatori matni (null — `app.boot.loading`). */
  loadingText: { type: String, default: null },
  /** Qator bosilganda ochiladi — hoverda ko‘rsatkich (pointer). */
  clickable: { type: Boolean, default: false },
})

const emit = defineEmits(['row-click'])

const { tr } = useI18n()

const loadingMessage = computed(() => props.loadingText ?? tr('app.boot.loading'))
const actionsHeading = computed(() => props.actionsLabel ?? tr('table.actions'))
</script>

<template>
  <div class="data-table" :class="{ 'data-table--clickable': clickable }">
    <table>
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key" :style="col.width ? { width: col.width } : {}">
            {{ col.label }}
          </th>
          <th v-if="$slots.actions" class="data-table__actions-col">{{ actionsHeading }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="data-table__placeholder">
            {{ loadingMessage }}
          </td>
        </tr>
        <tr v-else-if="rows.length === 0">
          <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="data-table__placeholder">
            {{ emptyText }}
          </td>
        </tr>
        <tr
          v-for="row in rows"
          v-else
          :key="row[rowKey]"
          @click="emit('row-click', row)"
        >
          <td v-for="col in columns" :key="col.key" :data-label="col.label">
            <slot :name="`cell:${col.key}`" :row="row" :value="row[col.key]">
              {{ col.formatter ? col.formatter(row[col.key], row) : row[col.key] }}
            </slot>
          </td>
          <td
            v-if="$slots.actions"
            class="data-table__actions-col"
            :data-label="actionsHeading"
            @click.stop
          >
            <slot name="actions" :row="row" />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
