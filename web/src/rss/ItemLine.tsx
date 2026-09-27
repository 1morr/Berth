import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { FeedItem } from '../api/rss'
import { Dot } from '../components/Dot'
import { episodeCode } from '../components/episodes'
import { whenText } from '../components/queueText'
import { SIGNAL_FILL } from '../components/signal'
import { JobLink } from '../jobs/JobLink'
import { skipText } from './skip'

/**
 * 一筆 Feed Item：狀態色塊、發佈名、集數、發佈時間、送出去的那一筆 Job、為什麼沒下載。
 *
 * 「最近的 Feed Item」與 RSS Series 展開的清單（M4 票 13）共用；前者多一行 `source`（來自哪個 Feed、
 * 屬於哪個 Series），後者整份都是同一個 Series，不說。放在 `gap-px bg-rule` 的 `ul` 裡。
 */
export function ItemLine({ row, source }: { row: FeedItem; source?: ReactNode }) {
  const { t, i18n } = useTranslation()

  return (
    <li className="grid min-w-0 gap-1 bg-well px-4 py-2.5">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <ItemChip row={row} />
        <span className="value min-w-0 basis-full text-sm wrap-anywhere text-ink sm:flex-1 sm:basis-auto">
          {row.title}
        </span>
      </div>
      <p className="text-xs text-ink-dim">
        {row.episode !== null && (
          <>
            <span className="value text-ink">{episodeCode(row.episode)}</span> <Dot />{' '}
          </>
        )}
        {t('rss.items.published')}{' '}
        <span className="value">
          {row.published_at ? whenText(row.published_at, i18n.language) : '—'}
        </span>
        {row.job_hash && (
          <>
            {' '}
            <Dot /> <JobLink hash={row.job_hash}>{t('rss.items.job')}</JobLink>
          </>
        )}
      </p>
      {source && <p className="text-xs wrap-anywhere text-ink-dim">{source}</p>}
      {/* 排除與去重擋下的都不是錯誤（票 10）：一句「為什麼沒下載」，不塗漆。 */}
      {row.skip && (
        <p className="max-w-prose text-xs wrap-anywhere text-ink-dim">{skipText(t, row.skip)}</p>
      )}
      {row.error && <p className="value text-xs wrap-anywhere text-ink">{row.error}</p>}
    </li>
  )
}

/**
 * 一筆 Item 的狀態色塊。**常態不塗漆**：待綁定已經在第一段塗過了，已送單是沒事，已排除與重複是
 * 照使用者的規則與帳本擋下的（票 10，不是錯誤）；只有送不出去
 * （`matched` 帶著原文）塗 `assigned`——卡住了、下一輪會再送，但原因（Route 紅燈、磁碟門檻）
 * 多半要人去修（DESIGN.md：卡住是 `assigned`，`blocked` 留給失敗）。
 */
function ItemChip({ row }: { row: FeedItem }) {
  const { t } = useTranslation()
  const stuck = row.status === 'matched' && row.error !== ''
  const key = stuck ? 'stuck' : row.status
  return (
    <span className={`label px-2 py-1 ${stuck ? SIGNAL_FILL.assigned : SIGNAL_FILL.neutral}`}>
      {t(`rss.items.status.${key}`)}
    </span>
  )
}
