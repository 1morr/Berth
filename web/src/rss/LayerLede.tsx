import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { exclusionsQueryOptions } from '../api/rss'
import { TEXT_LINK } from '../components/controls'

/** 全域那一段（`ExclusionsSection`）的錨點：這裡的合集那一行連到它（M4 票 113）。 */
export const GLOBAL_EXCLUSIONS_ANCHOR = 'global-exclusions'

/**
 * Feed 與 RSS Series 那一層的說明：這一層與其他層的關係，加上全域的合集設定。
 *
 * 這兩層沒有合集開關（brief §15 定在全域；票 113〈不做〉）：第二行說出全域那一項的目前值、
 * 連回全域那一段，免得看起來像這一層漏了（M4 票 113）。讀的是全域那一段同一個查詢，切換全域開關後
 * 一起重問、跟著變。
 */
export function LayerLede({ lede }: { lede: string }) {
  const { t } = useTranslation()
  const global = useQuery(exclusionsQueryOptions())

  return (
    <div className="grid max-w-prose gap-1 text-xs text-ink-dim">
      <p>{lede}</p>
      {global.data && (
        <p className="flex flex-wrap items-center gap-x-2">
          <span>
            {global.data.not_single ? t('rss.rules.notSingleOn') : t('rss.rules.notSingleOff')}
          </span>
          <a href={`#${GLOBAL_EXCLUSIONS_ANCHOR}`} className={TEXT_LINK}>
            {t('rss.rules.toGlobal')}
          </a>
        </p>
      )}
    </div>
  )
}
