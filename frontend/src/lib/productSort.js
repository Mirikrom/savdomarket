/**
 * Backend: ProductViewSet.order_by("-id") — yangi mahsulotlar yuqorida.
 * Offline vaqtincha (manfiy) ID lar ham shu tartibda joylashadi.
 */
export function productDisplaySortKey(product) {
  const id = Number(product?.id) || 0
  if (id < 0) return Math.abs(id)
  return id
}

export function compareProductsDisplayOrder(a, b) {
  return productDisplaySortKey(b) - productDisplaySortKey(a)
}

export function sortProductsForDisplay(products) {
  return [...products].sort(compareProductsDisplayOrder)
}

/** № ustuni: eng eski = 1 */
export function compareProductsCreationOrder(a, b) {
  return productDisplaySortKey(a) - productDisplaySortKey(b)
}
