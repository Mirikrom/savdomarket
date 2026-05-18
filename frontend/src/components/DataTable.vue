<script setup>
defineProps({
  columns: { type: Array, required: true }, // [{key, label, formatter?, width?}]
  rows: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  rowKey: { type: String, default: 'id' },
  emptyText: { type: String, default: 'Ma\u2019lumot topilmadi.' },
  /** Amallar ustuni sarlavhasi (bo‘sh — faqat ikonka ustuni). */
  actionsLabel: { type: String, default: 'Amallar' },
  /** Qator bosilganda ochiladi — hoverda ko‘rsatkich (pointer). */
  clickable: { type: Boolean, default: false },
})

const emit = defineEmits(['row-click'])
</script>

<template>
  <div class="data-table" :class="{ 'data-table--clickable': clickable }">
    <table>
      <thead>
        <tr>
          <th v-for="col in columns" :key="col.key" :style="col.width ? { width: col.width } : {}">
            {{ col.label }}
          </th>
          <th v-if="$slots.actions" class="data-table__actions-col">{{ actionsLabel }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="data-table__placeholder">
            Yuklanmoqda...
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
          <td v-for="col in columns" :key="col.key">
            <slot :name="`cell:${col.key}`" :row="row" :value="row[col.key]">
              {{ col.formatter ? col.formatter(row[col.key], row) : row[col.key] }}
            </slot>
          </td>
          <td v-if="$slots.actions" class="data-table__actions-col" @click.stop>
            <slot name="actions" :row="row" />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
