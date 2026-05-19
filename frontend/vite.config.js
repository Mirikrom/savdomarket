import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import basicSsl from '@vitejs/plugin-basic-ssl'
import { VitePWA } from 'vite-plugin-pwa'

// Host port (.env FRONTEND_PUBLISH_PORT) — lokal va prod bir xil: 51711
const frontendPublishPort = Number(process.env.FRONTEND_PUBLISH_PORT || 51711)

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    basicSsl(),
    VitePWA({
      registerType: 'autoUpdate',
      injectRegister: 'auto',
      devOptions: {
        // Self-signed SSL da Service Worker xato beradi — faqat production build
        enabled: false,
      },
      includeAssets: ['savdopro-logo-black.png', 'savdopro-logo-white.png'],
      manifest: {
        name: 'SavdoPro',
        short_name: 'SavdoPro',
        description: 'Savdo va ombor boshqaruvi',
        theme_color: '#1f4fa3',
        background_color: '#f1f5f9',
        display: 'standalone',
        lang: 'uz',
        start_url: '/',
        icons: [
          {
            src: '/savdopro-logo-black.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/savdopro-logo-white.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api/, /^\/media/, /^\/admin/],
        // API keshi backend o‘chganda ham “onlayn” ko‘rsatardi — mahsulotlar IndexedDB dan.
      },
    }),
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    https: true,
    hmr: {
      clientPort: frontendPublishPort,
      protocol: 'wss',
    },
    // Backend so'rovlarini Vite orqali backend container'iga proxy qilamiz.
    // Brauzer host porti: FRONTEND_PUBLISH_PORT (51711) — CORS muammosi kamayadi.
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/media': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
})
