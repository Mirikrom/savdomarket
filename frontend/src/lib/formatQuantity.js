/**
 * Sotuv/ombor miqdorini inson uchun qisqa ko‘rsatish.
 * API Decimal "100.000" → "100"; kasr bo‘lsa (masalan kg) — ortiqcha nollar yo‘q.
 */
export function formatQuantity(n) {
  const num = Number(n)
  if (!Number.isFinite(num)) return n == null || n === '' ? '' : String(n)
  if (Number.isInteger(num)) return String(num)
  return num.toLocaleString('uz-UZ', {
    maximumFractionDigits: 3,
    minimumFractionDigits: 0,
  })
}
