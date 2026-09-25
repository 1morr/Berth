import type { TFunction } from 'i18next'

import type { SeriesCorrected } from '../api/files'

/** 一個 RSS Series 的季號與集號偏移：審核的組、計劃與改正之後的結果都用這兩格（M3 票 13）。 */
export interface SeriesValues {
  season: number | null
  episode_offset: number | null
}

/** 偏移帶正負號（`+12`、`-3`）：與後端 `series_corrected` 理由裡的 `offset` 同一種寫法。 */
export function signedOffset(offset: number): string {
  return offset > 0 ? `+${offset}` : String(offset)
}

/**
 * 「第 1 季、集號偏移 +12」。兩格都沒設時回 `null`：那是「由解析器判斷」，每個呼叫端說法不同
 * （計劃是一整句、審核的組是一格的值），由它們自己說。
 */
export function seriesValuesText(t: TFunction, values: SeriesValues): string | null {
  const { season, episode_offset: offset } = values
  if (season !== null && offset !== null) {
    return t('rss.values.both', { season, offset: signedOffset(offset) })
  }
  if (season !== null) return t('rss.values.season', { season })
  if (offset !== null) return t('rss.values.offset', { offset: signedOffset(offset) })
  return null
}

/**
 * 套用到 RSS Series 之後的那一句：Series 現在的值，接著其餘的集數怎麼了——跟著搬的、重新規劃的、搬不過去
 * 留下的，是 0 的不說；三個都是 0 時說沒有別的要改，免得使用者以為其餘的被漏掉了。
 */
export function seriesCorrectedText(t: TFunction, series: SeriesCorrected): string {
  const followed = [
    series.moved > 0 ? t('rematch.series.moved', { count: series.moved }) : '',
    series.replanned > 0 ? t('rematch.series.replanned', { count: series.replanned }) : '',
    series.left > 0 ? t('rematch.series.left', { count: series.left }) : '',
  ].filter(Boolean)
  return [
    // 套用之後季號一定有（人填的那一格），所以不會落到「由解析器判斷」。
    t('rematch.series.set', { values: seriesValuesText(t, series) ?? '' }),
    ...(followed.length > 0 ? followed : [t('rematch.series.nothingElse')]),
  ].join(' ')
}
