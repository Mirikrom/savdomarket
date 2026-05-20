<script setup>
import PageHeader from '../../components/PageHeader.vue'
import { useI18n } from '../../i18n'

const { tr } = useI18n()
</script>

<template>
  <div>
    <PageHeader :title="tr('page.reports.title')" :subtitle="tr('page.reports.subtitle')" />
    <div class="placeholder">
      <h2>{{ tr('page.reports.placeholderTitle') }}</h2>
      <p>
        {{ tr('page.reports.placeholderBody') }}
      </p>
    </div>
  </div>
</template>
