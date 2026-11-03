import { useId } from 'react'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { ScheduleCard } from '../api/schedule'
import { ArtSlot } from '../components/ArtSlot'
import { episodeCode, seasonCode } from '../components/episodes'
import { displayRound } from '../i18n/displayRound'

/** 縮圖的寬度（`w-12`）：`srcset` 照它挑 TMDB 的哪一個寬度。 */
const THUMB_SIZES = '3rem'

/**
 * 時間表上的一張卡（M5.5 票 09，`.scratch/m5.5/schedule-shape.md`）：小海報橫列，一部一列。
 *
 * 整列一條連結到作品頁（訂閱走那裡的現有流程），名字是作品名，集數與狀態是 `aria-describedby`——
 * 與牆卡片同一個規矩（DESIGN.md〈牆卡片〉），控制項清單上每一條都從作品名念起。
 *
 * 狀態：未訂閱**不畫色塊**（大多數卡片都是它，The Usual Stays Unpainted Rule），已訂閱與已入庫是
 * 中性小色塊——它們是事實，不是四個信號色裡的任何一個。
 */
export function ScheduleCardRow({ card }: { card: ScheduleCard }) {
  const { t, i18n } = useTranslation()
  const title = displayRound(i18n.language, { 'zh-Hant': card.title, en: card.title_en })
  const poster = displayRound(i18n.language, { 'zh-Hant': card.poster_url, en: card.poster_url_en })
  const factsId = useId()

  return (
    <Link
      to="/media/$mediaId"
      params={{ mediaId: card.media_id }}
      aria-label={title}
      aria-describedby={factsId}
      className="grid grid-cols-[3rem_1fr] items-start gap-3 border-2 border-rule bg-well p-2 hover:border-rule-strong"
    >
      <ArtSlot url={poster} shape="poster" sizes={THUMB_SIZES} />
      <div className="grid min-w-0 content-start gap-1">
        <h3 className="value line-clamp-2 text-sm leading-snug text-ink">{title}</h3>
        <p id={factsId} className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="value text-xs text-ink-dim">{`${seasonCode(card.season)}${episodeCode(card.episode)}`}</span>
          {/* 空白讓描述念成「S02E05 已訂閱」而不是黏在一起；畫面上的間距是 `gap`。 */}
          {card.status !== 'unsubscribed' && ' '}
          {card.status !== 'unsubscribed' && (
            <span className="label bg-deck px-1.5 py-0.5 text-ink">
              {t(`schedule.status.${card.status}`)}
            </span>
          )}
        </p>
      </div>
    </Link>
  )
}
