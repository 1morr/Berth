import { useTranslation } from 'react-i18next'

import { setLanguage } from '../i18n'
import { SUPPORTED_LANGUAGES, type Language } from '../i18n/resources'

const CODE = { 'zh-Hant': 'language.zh', en: 'language.en' } as const

/** 橫幅右上角的雙字碼。選擇存 localStorage（shape brief §6）。 */
export function LanguageToggle() {
  const { t, i18n } = useTranslation()

  return (
    <div
      role="group"
      aria-label={t('language.label')}
      className="flex items-stretch gap-px bg-rule"
    >
      {SUPPORTED_LANGUAGES.map((language: Language) => {
        const current = i18n.language === language
        return (
          <button
            key={language}
            type="button"
            aria-pressed={current}
            onClick={() => setLanguage(language)}
            // `min-h-6`：WCAG 2.2 的 24px 命中面積，兩顆之間只有 1px 縫，間距例外不成立（票 15）。
            //
            // 選中態是中性色塊（`deck` 底 + 滿版 `ink`，同頁首的角色色塊），不是 `assigned` 黃漆：
            // 語言是角色不是狀態，而黃漆的語意是「現在需要你」（DESIGN.md 的 The Role Is Not A
            // State Rule；M1 critique 指出常駐的那一塊黃稀釋了它）。未選中往下沉一階到 `well`，
            // 兩顆的差別是底色與字色兩層，另有 `aria-pressed` 給輔助技術。
            className={`label inline-flex min-h-6 items-center px-2.5 py-1.5 ${
              current ? 'bg-deck text-ink' : 'bg-well text-ink-dim hover:text-ink'
            }`}
          >
            {t(CODE[language])}
          </button>
        )
      })}
    </div>
  )
}
