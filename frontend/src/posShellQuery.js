/**
 * Kassa (CashierLayout) ichidagi tablar — `?pos=1` bilan.
 * Admin: boshqaruv panelidan `/app/sales` (so‘rovsiz) → to‘liq layout; POS dan xuddi shu yo‘l + `pos=1` → kassa shell.
 */
export const POS_SHELL_QUERY_KEY = 'pos'
export const POS_SHELL_QUERY_VALUE = '1'

export const posShellQuery = Object.freeze({
  [POS_SHELL_QUERY_KEY]: POS_SHELL_QUERY_VALUE,
})

/** String path uchun RouterLink `to` obyekti */
export function routeWithPosShell(path) {
  return { path, query: { ...posShellQuery } }
}

/** Named route + POS query */
export function routeNameWithPosShell(name, extraQuery = {}) {
  return { name, query: { ...posShellQuery, ...extraQuery } }
}
