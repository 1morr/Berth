import { useTranslation } from 'react-i18next'

import type { SkippedSite } from '../api/search'
import { Notice } from '../components/controls'
import { Timestamp } from '../components/Timestamp'

/**
 * 請求預算放不下這一批、這次沒問的站（M4 票 77）。其他站照常問了，所以這是結果旁邊的一句說明，
 * 不是錯誤：配 `neutral`（不需要你，也還沒完成），與「等請求預算」同一種顏色。
 *
 * 每一站都放不下時是 `IndexerNotice` 的「等請求預算」，這裡不再逐站列一次。站名是索引站裡的名字，
 * 主機名是預算的鍵（健康頁的「請求預算」以它列），兩個都給，對得起來。
 */
export function SkippedSites({ skipped }: { skipped: SkippedSite[] }) {
  const { t } = useTranslation()
  if (skipped.length === 0) return null

  return (
    <div className="grid max-w-prose gap-2">
      <Notice signal="neutral" label={t('search.skipped.label')}>
        {t('search.skipped.body', { count: skipped.length })}
      </Notice>
      <ul aria-label={t('search.skipped.label')} className="grid gap-1 text-xs text-ink-dim">
        {skipped.map((one) => (
          <li key={one.site} className="flex flex-wrap gap-x-2">
            {one.indexers.length > 0 && (
              <span className="text-ink">{one.indexers.join(' · ')}</span>
            )}
            <span className="value">{one.site}</span>
            <span>
              {one.until ? (
                <>
                  {t('search.skipped.fitsAt')} <Timestamp at={one.until} />
                </>
              ) : (
                t('search.skipped.never')
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
