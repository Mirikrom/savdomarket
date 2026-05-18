/**
 * PC mahalliy vaqti (Toshkent = brauzer soati).
 * toISOString() UTC ga o‘giradi (10:08 → 05:08Z) — bazada PC bilan farq qiladi.
 */
export function localDateTimeIso(date = new Date()) {
  const d = date instanceof Date ? date : new Date(date)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}
