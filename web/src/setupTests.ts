import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'

import i18n from './i18n'

// vitest 沒開 globals，testing-library 的自動清理不會註冊，上一個測試的 DOM 會留著。
afterEach(cleanup)

// jsdom 的 `navigator.language` 是 en-US，語言偵測會落到 en。測試固定用 zh-Hant，
// 想驗英文的測試自己 changeLanguage。
beforeEach(() => {
  void i18n.changeLanguage('zh-Hant')
})
