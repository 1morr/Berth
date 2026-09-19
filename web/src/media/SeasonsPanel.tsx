import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import { COMPACT_BUTTON, NAV_BOX, NAV_BOX_ACTIVE } from '../components/controls'
import { missingOf } from './missing'
import { SeasonList } from './SeasonList'

/**
 * 季集與入庫（Berth 的季表，Media 詳情區塊序列的第 3 塊，`.scratch/m1.5/media-detail-shape.md` §3）。
 *
 * 它回答的是「TMDB 上有幾季幾集、磁碟上有哪幾集」——與上面的觀看區各說一件事，不合併
 * （合併要以季集號對齊兩個來源，Jellyfin 認錯編號時整列對歪）。
 *
 * 標題列下方一條**工具列**（shape §4）：「只看缺集」與「搜這部作品缺的集」（票 10）都在這裡。
 * 沒有東西可以篩的時候不畫、不留高度——電影與還沒有任何一季的作品都沒有。
 *
 * **篩選是這一部作品當下的視角，不寫進網址**：它不換資料、不分頁，也沒有人要分享「只看缺集的那一頁」
 * （媒體庫牆的篩選寫網址是因為它換的是後端的查詢並且會翻頁，票 06）。也因為它只屬於這一部作品，
 * 呼叫端要給 `key`——`/media/$mediaId` 是同一條路由，少了它篩選會跟著換過去的那一部走（票 09b）。
 */
export function SeasonsPanel({
  media,
  onSearchMissing,
}: {
  media: Media
  /** 缺集一鍵搜：整部作品是 `null`，一季是那一季的季號（M1.5 票 10）。 */
  onSearchMissing: (season: number | null) => void
}) {
  const { t } = useTranslation()
  const headingId = useId()
  const [missingOnly, setMissingOnly] = useState(false)
  const listed = media.kind !== 'movie' && media.seasons.length > 0
  const total = media.seasons.reduce((sum, season) => sum + missingOf(season).length, 0)

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h2 id={headingId} className="label text-ink">
          {t('media.seasons')}
        </h2>
        {media.seasons.length > 0 && (
          <p className="value text-xs text-ink-dim">{media.seasons.length}</p>
        )}
      </div>

      {listed && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <button
            type="button"
            aria-pressed={missingOnly}
            onClick={() => setMissingOnly(!missingOnly)}
            className={`${missingOnly ? NAV_BOX_ACTIVE : NAV_BOX} inline-flex min-h-6 items-center px-3 py-1.5 text-ink`}
          >
            {t('media.season.missingOnly')}
          </button>
          {/* 缺集一鍵搜（票 10）：**沒有缺集時整顆不畫**——按了也沒有東西可搜。按下去不在這裡
              另開結果表，它把查詢交給上面那一個搜尋區塊（shape §4）。 */}
          {total > 0 && (
            <button type="button" onClick={() => onSearchMissing(null)} className={COMPACT_BUTTON}>
              {t('media.season.searchMissing')}
            </button>
          )}
          {/* 一直在 DOM 裡：`aria-live` 要先存在，之後換進去的字才會被念出來。 */}
          <p aria-live="polite" className="value text-xs text-ink">
            {missingOnly &&
              (total > 0
                ? t('media.season.missingTotal', { count: total })
                : t('media.season.noneMissingAnywhere'))}
          </p>
        </div>
      )}

      {media.kind === 'movie' ? (
        // 電影沒有季集區塊（票 04 驗收）。說一句話，不留一塊空白。
        <p className="max-w-prose text-sm text-ink-dim">{t('media.season.film')}</p>
      ) : listed ? (
        <SeasonList
          seasons={media.seasons}
          missingOnly={missingOnly}
          onSearchMissing={onSearchMissing}
        />
      ) : (
        <p className="max-w-prose text-sm text-ink-dim">{t('media.season.none')}</p>
      )}
    </section>
  )
}
