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
    // 預設 5 s。放寬的代價只有「真的壞掉的測試要多等幾秒才紅」；不放寬的代價是機器忙的時候
    // 偶發紅燈，而偶發紅燈會教人重跑一次而不是去看它（M2 票 02）。
    // **`findBy*` 不看這一個**——它走 testing-library 的 `asyncUtilTimeout`（`src/setupTests.ts`）。
    testTimeout: 15_000,
  },
})
