<script setup>
import BrandLogo from './BrandLogo.vue'
import { formatQuantity } from '../lib/formatQuantity'

defineProps({
  sale: { type: Object, required: true },
})

const PAYMENT_LABEL = {
  cash: 'Naqd',
  card: 'Karta',
  mixed: 'Aralash',
  transfer: 'O‘tkazma',
}

function formatMoney(n) {
  return Number(n || 0).toLocaleString('uz-UZ', { maximumFractionDigits: 0 })
}

function paymentLabel(method) {
  return PAYMENT_LABEL[method] || method || '—'
}
</script>

<template>
  <div id="sale-receipt-print" class="receipt receipt-print-area">
    <div class="receipt__head">
      <BrandLogo variant="receipt" />
      <small v-if="sale.sold_at">{{ new Date(sale.sold_at).toLocaleString('uz-UZ') }}</small>
      <small>Chek #{{ sale.id }}</small>
      <small v-if="sale.branch_name">{{ sale.branch_name }}</small>
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
      <div><span>Subtotal:</span><strong>{{ formatMoney(sale.subtotal) }}</strong></div>
      <div v-if="Number(sale.discount) > 0">
        <span>Chegirma:</span><strong>-{{ formatMoney(sale.discount) }}</strong>
      </div>
      <div class="receipt__final"><span>Jami:</span><strong>{{ formatMoney(sale.total) }} so‘m</strong></div>
      <div v-if="sale.debtor_name"><span>Qarzdor:</span><strong>{{ sale.debtor_name }}</strong></div>
      <div><span>To‘langan:</span><strong>{{ formatMoney(sale.paid) }}</strong></div>
      <div v-if="Number(sale.balance_due) > 0">
        <span>Qarz:</span><strong>{{ formatMoney(sale.balance_due) }} so'm</strong>
      </div>
      <div v-if="Number(sale.change) > 0">
        <span>Qaytim:</span><strong>{{ formatMoney(sale.change) }}</strong>
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
