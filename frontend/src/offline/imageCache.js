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

export async function attachCachedImagesToProducts(products) {
  if (!products?.length) return products
  const ids = products.map((p) => p.id)
  const rows = await savdoDb.product_images.bulkGet(ids)
  for (let i = 0; i < products.length; i++) {
    const row = rows[i]
    const p = products[i]
    if (!row?.blob) continue
    let url = blobUrlByProductId.get(p.id)
    if (!url) {
      url = URL.createObjectURL(row.blob)
      blobUrlByProductId.set(p.id, url)
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
