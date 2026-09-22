import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'

import i18n from './i18n'

// `findBy*` 與 `waitFor` 的預設逾時是 1 秒，而它在**機器忙的時候**不夠：一次全量跑要掛
// 四百多個元件，而這台機器同時會有好幾個 worktree 在跑自己的測試。這裡放寬到 5 秒
// （M2 票 02）。**它不在 `vite.config.ts`**：vitest 的 `testTimeout` 管的是整個 test，
// 這一個是 testing-library 自己的設定，只有 `configure()` 進得去。
configure({ asyncUtilTimeout: 5_000 })

// vitest 沒開 globals，testing-library 的自動清理不會註冊，上一個測試的 DOM 會留著。
afterEach(cleanup)

// jsdom 的 `navigator.language` 是 en-US，語言偵測會落到 en。測試固定用 zh-Hant，
// 想驗英文的測試自己 changeLanguage。
beforeEach(() => {
  void i18n.changeLanguage('zh-Hant')
})
