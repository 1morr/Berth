import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// 後端預設的 port（berth/config.py 的 DEFAULT_PORT）。
const BACKEND = 'http://127.0.0.1:8383'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // 開發時前端跑在 Vite 上，/api 代理到後端；production 由同一個程序提供，不經過這裡。
    proxy: { '/api': BACKEND },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
    css: false,
  },
})
