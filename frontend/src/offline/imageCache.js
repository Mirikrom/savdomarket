import { savdoDb } from './db'

const blobUrlByProductId = new Map()

export function toAbsoluteMediaUrl(raw) {
  if (!raw || typeof raw !== 'string') return ''
  const s = raw.trim()
  if (!s) return ''
  if (/^https?:\/\//i.test(s) || s.startsWith('//')) return s
  const path = s.startsWith('/') ? s : `/${s}`
  if (typeof window === 'undefined') return path
  return new URL(path, window.location.origin).href
}

export function getCachedProductImageUrl(productId) {
  return blobUrlByProductId.get(productId) || ''
}

export function resolveProductImageSrc(product) {
  if (!product) return ''
  const cached = getCachedProductImageUrl(product.id)
  if (cached) return cached
  return toAbsoluteMediaUrl(product.image_url || product.image || product.thumbnail)
}

/** Offline qo‘shilgan mahsulot rasmini lokal keshga yozish (jadvalda ko‘rinishi uchun). */
export async function cacheLocalProductImageFile(productId, file) {
  if (!file || typeof window === 'undefined') return ''
  const pid = Number(productId)
  if (!Number.isFinite(pid)) return ''

  const blob = file instanceof Blob ? file : null
  if (!blob) return ''

  await savdoDb.product_images.put({
    productId: pid,
    blob,
    updated_at: Date.now(),
  })

  const prev = blobUrlByProductId.get(pid)
  if (prev) URL.revokeObjectURL(prev)
  const url = URL.createObjectURL(blob)
  blobUrlByProductId.set(pid, url)
  return url
}

export async function getLocalProductImageFile(productId) {
  const row = await savdoDb.product_images.get(Number(productId))
  if (!row?.blob) return null
  const type = row.blob.type || 'image/jpeg'
  if (row.blob instanceof File) return row.blob
  return new File([row.blob], `product-${productId}.jpg`, { type })
}

export async function migrateProductImageCache(fromId, toId) {
  const from = Number(fromId)
  const to = Number(toId)
  if (!Number.isFinite(from) || !Number.isFinite(to) || from === to) return

  const row = await savdoDb.product_images.get(from)
  if (!row?.blob) return

  await savdoDb.product_images.put({
    productId: to,
    blob: row.blob,
    updated_at: Date.now(),
  })
  await savdoDb.product_images.delete(from)

  const prevFrom = blobUrlByProductId.get(from)
  if (prevFrom) URL.revokeObjectURL(prevFrom)
  blobUrlByProductId.delete(from)

  const prevTo = blobUrlByProductId.get(to)
  if (prevTo) URL.revokeObjectURL(prevTo)
  blobUrlByProductId.set(to, URL.createObjectURL(row.blob))
}

export async function deleteLocalProductImage(productId) {
  const id = Number(productId)
  if (!Number.isFinite(id)) return
  await savdoDb.product_images.delete(id).catch(() => {})
  const prev = blobUrlByProductId.get(id)
  if (prev) URL.revokeObjectURL(prev)
  blobUrlByProductId.delete(id)
}

export async function productHasLocalImage(productId) {
  const row = await savdoDb.product_images.get(Number(productId))
  return Boolean(row?.blob)
}

export async function attachCachedImagesToProducts(products) {
  if (!products?.length) return products
  for (const p of products) {
    const pid = Number(p.id)
    if (!Number.isFinite(pid)) continue
    const row = await savdoDb.product_images.get(pid)
    if (!row?.blob) continue
    let url = blobUrlByProductId.get(pid)
    if (!url) {
      url = URL.createObjectURL(row.blob)
      blobUrlByProductId.set(pid, url)
    }
    p._cachedImageUrl = url
  }
  return products
}

async function fetchImageBlob(url) {
  const abs = toAbsoluteMediaUrl(url)
  if (!abs) return null
  const token = localStorage.getItem('access_token')
  const headers = {}
  if (token) headers.Authorization = `Bearer ${token}`
  const res = await fetch(abs, { credentials: 'same-origin', headers })
  if (!res.ok) return null
  return res.blob()
}

export async function cacheProductImages(products, { concurrency = 4 } = {}) {
  if (!products?.length || typeof window === 'undefined') {
    return { cached: 0, failed: 0 }
  }

  const withImages = products.filter((p) => p.image_url)
  let cached = 0
  let failed = 0
  let index = 0

  async function worker() {
    while (index < withImages.length) {
      const i = index++
      const p = withImages[i]
      try {
        const blob = await fetchImageBlob(p.image_url)
        if (!blob) {
          failed += 1
          continue
        }
        await savdoDb.product_images.put({
          productId: p.id,
          blob,
          updated_at: Date.now(),
        })
        const prev = blobUrlByProductId.get(p.id)
        if (prev) URL.revokeObjectURL(prev)
        blobUrlByProductId.set(p.id, URL.createObjectURL(blob))
        cached += 1
      } catch {
        failed += 1
      }
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, withImages.length) }, () => worker())
  await Promise.all(workers)
  return { cached, failed }
}

export async function pruneOrphanedImages(validProductIds) {
  const valid = new Set(validProductIds)
  const all = await savdoDb.product_images.toArray()
  const remove = all.filter((r) => !valid.has(r.productId)).map((r) => r.productId)
  if (remove.length) {
    await savdoDb.product_images.bulkDelete(remove)
    for (const id of remove) {
      const url = blobUrlByProductId.get(id)
      if (url) URL.revokeObjectURL(url)
      blobUrlByProductId.delete(id)
    }
  }
}
