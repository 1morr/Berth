import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'

import { SUPPORTED_LANGUAGES, resources, type Language } from './resources'

const STORAGE_KEY = 'berth.language'

/** 語言檔隨 bundle 一起送，沒有 backend 也沒有非同步載入，所以 init 是同步完成的。 */
export function detectLanguage(stored: string | null, preferred: readonly string[] = []): Language {
  const candidates = [stored, ...preferred].filter((tag): tag is string => Boolean(tag))
  for (const tag of candidates) {
    // `zh-TW`、`zh-Hant-HK`、`zh` 都算繁體中文；其餘語言目前一律落到 en。
    const match = SUPPORTED_LANGUAGES.find(
      (language) => tag === language || tag.toLowerCase().startsWith(language.toLowerCase() + '-'),
    )
    if (match) return match
    if (/^zh(-|$)/i.test(tag)) return 'zh-Hant'
  }
  return 'en'
}

function readStored(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    // 隱私模式與封鎖網站資料的瀏覽器會直接丟例外，語言偵測不該因此整頁掛掉。
    return null
  }
}

/** 語言換了就同步 `<html lang>`：`.label` 的中英兩種樣式靠 `:lang()` 分岔（index.css）。 */
function applyDocumentLanguage(language: string): void {
  document.documentElement.lang = language
}

export function setLanguage(language: Language): void {
  try {
    localStorage.setItem(STORAGE_KEY, language)
  } catch {
    // 存不下來只是下次要重選，不影響這一次的切換。
  }
  void i18next.changeLanguage(language)
}

// 關掉 Suspense：沒有非同步載入要等，多一層 boundary 只會讓測試與錯誤訊息更難讀。
void i18next.use(initReactI18next).init({
  lng: detectLanguage(readStored(), navigator.languages ?? [navigator.language]),
  fallbackLng: 'en',
  supportedLngs: SUPPORTED_LANGUAGES,
  defaultNS: 'translation',
  resources,
  interpolation: { escapeValue: false },
  react: { useSuspense: false },
})

applyDocumentLanguage(i18next.language)
i18next.on('languageChanged', applyDocumentLanguage)

export default i18next
