import { languageName } from './languageName'

/**
 * 替還沒初始化的 Jellyfin 跑它自己的初始精靈時寫進去的語言與地區（M4 票 18，後端
 * `jellyfin.JellyfinStartup`）。欄位名與 `POST /setup/owner` 的 body 一樣。
 */
export interface JellyfinLocale {
  /** `UICulture`：Jellyfin 的介面語言代碼。 */
  ui_culture: string
  /** `PreferredMetadataLanguage`。 */
  metadata_language: string
  /** `MetadataCountryCode`，ISO 3166 兩碼。 */
  metadata_country: string
}

/**
 * 畫面上能選的幾組。**語言與國家綁成一組**：Jellyfin 自己的精靈分兩頁問（介面語言、metadata 的語言與
 * 國家），擁有者表單裡問一格就夠——要細分的人去 Jellyfin 的控制台改。代碼是 Jellyfin 認的那一種
 * （英文的 metadata 語言是 `en`，不是 `en-US`）。
 */
export const JELLYFIN_LOCALES: readonly JellyfinLocale[] = [
  { ui_culture: 'zh-TW', metadata_language: 'zh-TW', metadata_country: 'TW' },
  { ui_culture: 'zh-HK', metadata_language: 'zh-HK', metadata_country: 'HK' },
  { ui_culture: 'zh-CN', metadata_language: 'zh-CN', metadata_country: 'CN' },
  { ui_culture: 'en-US', metadata_language: 'en', metadata_country: 'US' },
  { ui_culture: 'en-GB', metadata_language: 'en', metadata_country: 'GB' },
  { ui_culture: 'ja', metadata_language: 'ja', metadata_country: 'JP' },
  { ui_culture: 'ko', metadata_language: 'ko', metadata_country: 'KR' },
]

/** Berth 的 UI 語言對到的那一組：預設值，也是套件內那一台不問就用的。 */
export function localeForUi(uiLanguage: string): JellyfinLocale {
  const culture = uiLanguage.startsWith('zh') ? 'zh-TW' : 'en-US'
  return JELLYFIN_LOCALES.find((row) => row.ui_culture === culture)!
}

/** 選單上的名字，照 UI 語言：`中文（台灣）`、`British English`、`日文（日本）`。 */
export function localeLabel(locale: JellyfinLocale, uiLanguage: string): string {
  const language = locale.ui_culture.split('-')[0]
  return languageName(`${language}-${locale.metadata_country}`, uiLanguage)
}
