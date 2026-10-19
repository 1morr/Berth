import type { TFunction } from 'i18next'

import type { FeedInterval } from '../api/rss'

/** 後端多一檔、少一檔都是編譯錯誤：下拉選單的選項從這張表來（M4 票 109）。 */
const CHOICES: Record<FeedInterval, true> = {
  900: true,
  1800: true,
  3600: true,
  10800: true,
  21600: true,
  43200: true,
  86400: true,
}

/** 由短到長。整數的 key 照數字排序（ECMAScript 的屬性順序）。 */
export const FEED_INTERVALS = Object.keys(CHOICES).map(Number) as FeedInterval[]

/** 不帶間隔加的 Feed 是 15 分鐘（後端 `DEFAULT_INTERVAL_SEC`）。 */
export const DEFAULT_FEED_INTERVAL: FeedInterval = 900

export function isFeedInterval(seconds: number): seconds is FeedInterval {
  return Object.hasOwn(CHOICES, seconds)
}

/** 「15 分鐘」「1 小時」：整點的說小時，其他說分鐘。 */
export function intervalLabel(t: TFunction, seconds: number): string {
  const minutes = Math.round(seconds / 60)
  return minutes % 60 === 0
    ? t('rss.feeds.interval.hours', { count: minutes / 60 })
    : t('rss.feeds.interval.minutes', { count: minutes })
}
