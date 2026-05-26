/** Shtrix-kod / SKU bo‘yicha mahsulot qidirish (skaner aparat va kamera). */

export function normalizeScanCode(raw) {
  return String(raw || '')
    .trim()
    .replace(/\s/g, '')
}

export function findProductByScanCode(products, raw) {
  const code = normalizeScanCode(raw).toLowerCase()
  if (!code) return null

  const list = products || []

  const byBarcode = list.find(
    (p) => normalizeScanCode(p.barcode).toLowerCase() === code,
  )
  if (byBarcode) return byBarcode

  const bySku = list.find((p) => normalizeScanCode(p.sku).toLowerCase() === code)
  if (bySku) return bySku

  return (
    list.find((p) => {
      const b = normalizeScanCode(p.barcode).toLowerCase()
      return b && (b.includes(code) || code.includes(b))
    }) || null
  )
}
