<script setup>
import { computed } from 'vue'

import BrandLogo from './BrandLogo.vue'
import { formatQuantity } from '../lib/formatQuantity'
import { numberLocaleForUi, useI18n } from '../i18n'
import { useOrganizationStore } from '../stores/organization'

const props = defineProps({
  sale: { type: Object, required: true },
})

const org = useOrganizationStore()
const { tr, locale, branchName } = useI18n()

const dateLocale = computed(() => numberLocaleForUi(locale.value))

function formatMoney(n) {
  const num = Number(n || 0).toLocaleString(dateLocale.value, { maximumFractionDigits: 0 })
  return `${num} ${tr('page.billing.currencySom')}`
}

function paymentLabel(method) {
  if (method === 'cash') return tr('page.salesHistory.payCash')
  if (method === 'card') return tr('page.salesHistory.payCard')
  if (method === 'mixed') return tr('pos.payTab.mixed')
  if (method === 'transfer') return tr('page.debtors.methodTransfer')
  return method || '—'
}

const branchDisplay = computed(() =>
  branchName(props.sale?.branch_name, org.branches),
)
</script>

<template>
  <div id="sale-receipt-print" class="receipt receipt-print-area">
    <div class="receipt__head">
      <BrandLogo variant="receipt" />
      <small v-if="sale.sold_at">{{ new Date(sale.sold_at).toLocaleString(dateLocale) }}</small>
      <small>{{ tr('page.salesHistory.receiptLabel') }} #{{ sale.id }}</small>
      <small v-if="sale.branch_name">{{ branchDisplay }}</small>
    </div>
    <ul class="receipt__items">
      <li v-for="item in sale.items" :key="item.id">
        <div>{{ item.product_name }}</div>
        <div class="receipt__line-detail">
          <span>{{ formatQuantity(item.quantity) }} × {{ formatMoney(item.unit_price) }}</span>
          <span>{{ formatMoney(item.line_total) }}</span>
        </div>
      </li>
    </ul>
    <div v-if="sale.payments?.length" class="receipt__payments">
      <div v-for="p in sale.payments" :key="p.id" class="receipt__line-detail">
        <span>{{ paymentLabel(p.method) }}</span>
        <span>{{ formatMoney(p.amount) }}</span>
      </div>
    </div>
    <div class="receipt__totals">
      <div><span>{{ tr('pos.receiptSubtotal') }}</span><strong>{{ formatMoney(sale.subtotal) }}</strong></div>
      <div v-if="Number(sale.discount) > 0">
        <span>{{ tr('pos.receiptDiscount') }}</span><strong>-{{ formatMoney(sale.discount) }}</strong>
      </div>
      <div class="receipt__final"><span>{{ tr('pos.receiptTotal') }}</span><strong>{{ formatMoney(sale.total) }}</strong></div>
      <div v-if="sale.debtor_name"><span>{{ tr('page.salesHistory.metaDebtor') }}</span><strong>{{ sale.debtor_name }}</strong></div>
      <div><span>{{ tr('pos.receiptPaid') }}</span><strong>{{ formatMoney(sale.paid) }}</strong></div>
      <div v-if="Number(sale.balance_due) > 0">
        <span>{{ tr('pos.summaryCredit') }}</span><strong>{{ formatMoney(sale.balance_due) }}</strong>
      </div>
      <div v-if="Number(sale.change) > 0">
        <span>{{ tr('pos.receiptChange') }}</span><strong>{{ formatMoney(sale.change) }}</strong>
      </div>
    </div>
  </div>
</template>

<style scoped>
.receipt {
  font-family: 'Courier New', monospace;
  padding: 10px;
}

.receipt__head {
  display: flex;
  flex-direction: column;
  align-items: center;
  border-bottom: 1px dashed var(--text-muted);
  padding-bottom: 10px;
  margin-bottom: 10px;
  gap: 4px;
}

.receipt__head small {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.receipt__items {
  list-style: none;
  padding: 0;
  margin: 0 0 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.receipt__payments {
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px dashed var(--text-muted);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.receipt__line-detail {
  display: flex;
  justify-content: space-between;
  color: var(--text-muted);
  font-size: 0.88rem;
}

.receipt__totals {
  border-top: 1px dashed var(--text-muted);
  padding-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.receipt__totals > div {
  display: flex;
  justify-content: space-between;
  font-size: 0.92rem;
}

.receipt__final {
  font-size: 1.05rem;
  border-top: 1px dashed var(--text-muted);
  padding-top: 6px;
  margin-top: 6px;
}
</style>

<style>
@media print {
  body * {
    visibility: hidden;
  }
  #sale-receipt-print,
  #sale-receipt-print * {
    visibility: visible;
  }
  #sale-receipt-print {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    padding: 12px;
  }
}
</style>
