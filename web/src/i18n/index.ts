import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'

import { resources } from './resources'

// 語言檔隨 bundle 一起送，沒有 backend 也沒有偵測器，所以 init 是同步完成的。
// 關掉 Suspense：沒有非同步載入要等，多一層 boundary 只會讓測試與錯誤訊息更難讀。
void i18next.use(initReactI18next).init({
  lng: 'zh-Hant',
  fallbackLng: 'zh-Hant',
  defaultNS: 'translation',
  resources,
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
})

export default i18next
