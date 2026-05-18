<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { BrowserMultiFormatReader } from '@zxing/browser'
import { BarcodeFormat, DecodeHintType } from '@zxing/library'

const props = defineProps({
  open: { type: Boolean, required: true },
  title: { type: String, default: 'Shtrix-kodni skaner qiling' },
})
const emit = defineEmits(['close', 'scanned'])

const videoEl = ref(null)
const error = ref('')
const cameras = ref([])
const cameraId = ref('')
const lastValue = ref('')
const torchOn = ref(false)
const torchSupported = ref(false)

let reader = null
let controls = null
let currentTrack = null

const hints = new Map()
hints.set(DecodeHintType.POSSIBLE_FORMATS, [
  BarcodeFormat.EAN_13,
  BarcodeFormat.EAN_8,
  BarcodeFormat.UPC_A,
  BarcodeFormat.UPC_E,
  BarcodeFormat.CODE_128,
  BarcodeFormat.CODE_39,
  BarcodeFormat.ITF,
  BarcodeFormat.QR_CODE,
])
hints.set(DecodeHintType.TRY_HARDER, true)

async function start() {
  error.value = ''
  lastValue.value = ''

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    error.value = 'Brauzer kamerani qo‘llab-quvvatlamaydi. HTTPS yoki localhost talab qilinadi.'
    return
  }

  try {
    reader = new BrowserMultiFormatReader(hints, { delayBetweenScanAttempts: 200 })

    // Maxsus kamera tanlanmagan bo'lsa, constraints orqali ishga tushiramiz
    // (telefonda orqa kamera afzal). Bu yo'l avtomatik ruxsat so'raydi va
    // `enumerateDevices` ni chaqirish shart emas.
    const constraints = cameraId.value
      ? { video: { deviceId: { exact: cameraId.value } } }
      : { video: { facingMode: { ideal: 'environment' } } }

    controls = await reader.decodeFromConstraints(
      constraints,
      videoEl.value,
      (result, err, ctl) => {
        if (result) {
          const text = result.getText()
          if (text && text !== lastValue.value) {
            lastValue.value = text
            emit('scanned', text)
            setTimeout(() => {
              lastValue.value = ''
            }, 800)
          }
        }
        void err
        if (ctl) controls = ctl
      },
    )

    // Stream ulangach, mavjud kameralar ro'yxatini olish endi
    // foydalanuvchiga `label`'lar bilan ko'rinadi (ruxsat berildi).
    try {
      cameras.value = await BrowserMultiFormatReader.listVideoInputDevices()
    } catch {
      cameras.value = []
    }

    const stream = videoEl.value?.srcObject
    if (stream) {
      const track = stream.getVideoTracks?.()[0]
      currentTrack = track || null
      if (track && !cameraId.value) {
        const settings = track.getSettings?.() || {}
        cameraId.value = settings.deviceId || ''
      }
      const cap = track?.getCapabilities?.()
      torchSupported.value = !!(cap && cap.torch)
    }
  } catch (e) {
    error.value = formatError(e)
  }
}

function stop() {
  try {
    if (controls && typeof controls.stop === 'function') controls.stop()
  } catch {
    // ignore
  }
  controls = null

  try {
    const stream = videoEl.value?.srcObject
    if (stream && stream.getTracks) {
      for (const t of stream.getTracks()) t.stop()
    }
    if (videoEl.value) videoEl.value.srcObject = null
  } catch {
    // ignore
  }
  currentTrack = null
  torchOn.value = false
  torchSupported.value = false
  reader = null
}

function formatError(e) {
  const name = e?.name || ''
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return 'Brauzer kamera ruxsatini bermadi. Saytni qayta yuklang va so‘ralganda “Ruxsat berish”ni tanlang.'
  }
  if (name === 'NotFoundError') {
    return 'Kamera topilmadi. Qurilmada kamera bormi va boshqa ilova band qilmaganligini tekshiring.'
  }
  if (name === 'OverconstrainedError') {
    return 'Tanlangan kamera mos kelmadi. Boshqa kamerani tanlang yoki ramkani yangilang.'
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return 'Kamerani boshqa dastur band qilgan. Boshqa ilovalarni yoping va qayta urinib ko‘ring.'
  }
  if (name === 'SecurityError') {
    return 'Xavfsiz ulanish (HTTPS) talab qilinadi. Saytga https:// orqali kiring.'
  }
  return e?.message || 'Kamera ulashda xatolik. Brauzer va qurilma sozlamalarini tekshiring.'
}

async function switchCamera(deviceId) {
  cameraId.value = deviceId
  stop()
  await start()
}

async function toggleTorch() {
  if (!currentTrack || !torchSupported.value) return
  try {
    torchOn.value = !torchOn.value
    await currentTrack.applyConstraints({ advanced: [{ torch: torchOn.value }] })
  } catch {
    torchOn.value = false
  }
}

function close() {
  stop()
  emit('close')
}

watch(
  () => props.open,
  (val) => {
    if (val) {
      // DOM render bo'lishi uchun kichik kechikish
      setTimeout(start, 50)
    } else {
      stop()
    }
  },
)

onBeforeUnmount(stop)
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="scanner-backdrop" @click.self="close">
        <div class="scanner-card">
          <header class="scanner-head">
            <h3>{{ title }}</h3>
            <button class="modal-close" type="button" @click="close">×</button>
          </header>

          <div class="scanner-video-wrap">
            <video ref="videoEl" class="scanner-video" autoplay playsinline muted />
            <div class="scanner-overlay">
              <div class="scanner-frame" />
              <p class="scanner-hint">Shtrix-kodni ramka ichiga joylang</p>
            </div>
          </div>

          <div class="scanner-controls">
            <select
              v-if="cameras.length > 1"
              :value="cameraId"
              class="scanner-select"
              @change="switchCamera($event.target.value)"
            >
              <option v-for="c in cameras" :key="c.deviceId" :value="c.deviceId">
                {{ c.label || `Kamera ${c.deviceId.slice(0, 6)}` }}
              </option>
            </select>

            <button
              v-if="torchSupported"
              type="button"
              class="btn btn--ghost btn--sm"
              @click="toggleTorch"
            >
              {{ torchOn ? 'Chiroqni o‘chirish' : 'Chiroq yoqish' }}
            </button>

            <button type="button" class="btn btn--ghost" @click="close">Yopish</button>
          </div>

          <p v-if="error" class="form-message form-message--error">{{ error }}</p>
          <p v-else-if="lastValue" class="form-message form-message--success">
            Topildi: {{ lastValue }}
          </p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.scanner-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

.scanner-card {
  background: var(--surface);
  border-radius: var(--radius);
  width: 100%;
  max-width: 520px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.3);
}

.scanner-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--line);
}

.scanner-head h3 {
  margin: 0;
  font-size: 1rem;
}

.scanner-video-wrap {
  position: relative;
  background: #000;
  aspect-ratio: 4 / 3;
  overflow: hidden;
}

.scanner-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.scanner-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.scanner-frame {
  width: 70%;
  height: 40%;
  border: 2px solid rgba(255, 255, 255, 0.9);
  border-radius: 12px;
  box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.25);
}

.scanner-hint {
  color: #fff;
  margin-top: 14px;
  font-size: 0.86rem;
  background: rgba(0, 0, 0, 0.45);
  padding: 4px 10px;
  border-radius: 999px;
}

.scanner-controls {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  align-items: center;
  flex-wrap: wrap;
}

.scanner-select {
  flex: 1;
  min-width: 160px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
  font-size: 0.88rem;
  outline: none;
}

.form-message {
  margin: 0 16px 14px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
