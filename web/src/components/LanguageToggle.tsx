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
            className={`label inline-flex min-h-6 items-center px-2.5 py-1.5 ${
              current ? 'bg-assigned text-on-signal' : 'bg-deck text-ink-dim hover:text-ink'
            }`}
          >
            {t(CODE[language])}
          </button>
        )
      })}
    </div>
  )
}
