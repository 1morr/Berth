import { useId } from 'react'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { ScheduleCard } from '../api/schedule'
import { ArtSlot } from '../components/ArtSlot'
import { Dot } from '../components/Dot'
import { episodeCode, seasonCode } from '../components/episodes'
import { displayRound } from '../i18n/displayRound'
import { airingTime } from './week'

/** 縮圖的寬度（`w-12`）：`srcset` 照它挑 TMDB 的哪一個寬度。 */
const THUMB_SIZES = '3rem'

/**
 * 時間表上的一張卡（M5.5 票 09，`.scratch/m5.5/schedule-shape.md`）：小海報橫列，一部一列。
 *
 * 整列一條連結到作品頁（訂閱走那裡的現有流程），名字是作品名，集數與狀態是 `aria-describedby`——
 * 與牆卡片同一個規矩（DESIGN.md〈牆卡片〉），控制項清單上每一條都從作品名念起。
 *
 * 第二層（票 14）：放送時刻（AniList，只有還沒播的）接在集數後面，Bangumi 評分排最後；對不上的作品
 * 兩格都沒有。
 *
 * 狀態：未訂閱**不畫色塊**（大多數卡片都是它，The Usual Stays Unpainted Rule），已訂閱、已入庫與
 * 「晚 N 天」（票 12）是中性小色塊——它們是事實，不是四個信號色裡的任何一個；晚了在這一頁也是中性：
 * 一般使用者也看得到它，而他動不了手，`assigned`（需要你）對他不成立（`.scratch/m5.5/tracking-shape.md`）。
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
        {/* 長片名換行、不截斷（DESIGN.md〈Layout〉的手機那一條）：英文片名在 129px 的欄裡兩行放不下。 */}
        <h3 className="value text-sm leading-snug wrap-anywhere text-ink">{title}</h3>
        <p id={factsId} className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="value text-xs wrap-anywhere text-ink-dim">{`${seasonCode(card.season)}${episodeCode(card.episode)}`}</span>
          {/* 空白讓描述念成「S02E05 23:00 已訂閱」而不是黏在一起；畫面上的間距是 `gap`。 */}
          {card.airs_at && (
            <>
              {' '}
              <Dot />
              <time dateTime={card.airs_at} className="value text-xs text-ink-dim">
                {airingTime(card.airs_at, card.air_date, i18n.language)}
              </time>
            </>
          )}
          {card.status !== 'unsubscribed' && ' '}
          {card.status !== 'unsubscribed' && (
            <span className="label bg-deck px-1.5 py-0.5 text-ink">
              {card.status === 'late'
                ? t('schedule.late', { count: card.late_days ?? 0 })
                : t(`schedule.status.${card.status}`)}
            </span>
          )}
          {card.score !== null && card.votes !== null && (
            <Rating score={card.score} votes={card.votes} />
          )}
        </p>
      </div>
    </Link>
  )
}

/**
 * Bangumi 評分：畫面上是「Bangumi 8.1」、人數放 `title`；念的是一整句「Bangumi 評分 8.1，900 人打分」
 * （畫面那一份對螢幕閱讀器藏起來，否則分數會念兩次）。
 */
function Rating({ score, votes }: { score: number; votes: number }) {
  const { t, i18n } = useTranslation()
  const shown = score.toLocaleString(i18n.language, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
  return (
    <>
      {' '}
      <span
        aria-hidden="true"
        className="value text-xs text-ink-dim"
        title={t('schedule.votes', { count: votes })}
      >
        {t('schedule.rating', { score: shown })}
      </span>
      <span className="sr-only">{t('schedule.ratingSpoken', { score: shown, count: votes })}</span>
    </>
  )
}
