import { useTranslation } from 'react-i18next'

import tmdbLogo from '../assets/tmdb.svg'

/**
 * TMDB 的標誌與那一句聲明（brief §20.3）。它是法定聲明，不是頁尾裝飾：資料來自 TMDB 的每一頁（探索、媒體庫、
 * 詳情）都要有。
 *
 * **一份**（票 13）：三頁原本各寫一次，`alt="TMDB"` 是硬寫的字，不走 i18n。
 */
export function TmdbAttribution() {
  const { t } = useTranslation()

  return (
    <footer className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t-2 border-rule pt-4">
      <img src={tmdbLogo} alt={t('discover.tmdbLogo')} height={16} className="h-4 w-auto" />
      <p className="max-w-prose text-xs text-ink-dim">{t('discover.attribution')}</p>
    </footer>
  )
}
