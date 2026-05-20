/**
 * Qora fon + oq SavdoPro logosi — PWA / favicon / apple-touch.
 * Ishga tushirish: npm run icons  (loyihada: npm install kerak)
 */
import { Jimp } from 'jimp'
import toIco from 'to-ico'
import { writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const publicDir = path.join(__dirname, '..', 'public')
const logoPath = path.join(publicDir, 'savdopro-logo-white.png')
/** slate-900 */
const BG_COLOR = 0x0f172aff

async function makeIcon(size, paddingRatio = 0.12) {
  const logo = await Jimp.read(logoPath)
  const pad = Math.round(size * paddingRatio)
  const inner = size - pad * 2

  logo.scaleToFit({ w: inner, h: inner })

  const bg = new Jimp({ width: size, height: size, color: BG_COLOR })
  const x = Math.round((size - logo.bitmap.width) / 2)
  const y = Math.round((size - logo.bitmap.height) / 2)
  bg.composite(logo, x, y)

  return bg.getBuffer('image/png')
}

const sizes = [
  { name: 'pwa-icon-192.png', size: 192 },
  { name: 'pwa-icon-512.png', size: 512 },
  { name: 'apple-touch-icon.png', size: 180 },
  { name: 'savdopro-pwa-icon.png', size: 512 },
]

for (const { name, size } of sizes) {
  const buf = await makeIcon(size)
  await writeFile(path.join(publicDir, name), buf)
  console.log('wrote', name)
}

const fav16 = await makeIcon(16, 0.06)
const fav32 = await makeIcon(32, 0.08)
const fav48 = await makeIcon(48, 0.1)

await writeFile(path.join(publicDir, 'favicon-32.png'), fav32)

const ico = await toIco([fav16, fav32, fav48])
await writeFile(path.join(publicDir, 'favicon.ico'), ico)
console.log('wrote favicon.ico')
