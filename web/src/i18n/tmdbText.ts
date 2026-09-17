import { SUPPORTED_LANGUAGES, type Language } from './resources'

/**
 * TMDB 的顯示用文字跟著 UI 語言走（brief §7.5）：`zh-Hant` 取 `zh-TW` 那一輪，`en` 取 `en-US` 那一輪。
 *
 * 後端兩輪都送（`title` / `title_en`、`overview` / `overview_en`），這裡只負責挑：換語言時畫面
 * 當場換掉，不必重抓。缺翻譯時的後備（`zh-TW` 缺就落回英文）後端已經做完，這裡不再補一層。
 * 每種 UI 語言都是必填的鍵，之後多一種語言時每個呼叫端都要補上它那一輪才編譯得過。
 */
export function tmdbText(language: string, rounds: Record<Language, string>): string {
  // 認不得的語言照 i18next 的 `fallbackLng` 落到 en。
  return isLanguage(language) ? rounds[language] : rounds.en
}

function isLanguage(value: string): value is Language {
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(value)
}
