/** 相對時間的說法（`Timestamp` 用）。拆成自己一個模組：元件檔只匯出元件，fast refresh 才認得。 */

const UNITS: ReadonlyArray<[Intl.RelativeTimeFormatUnit, number]> = [
  ['second', 60],
  ['minute', 60],
  ['hour', 24],
  ['day', 7],
]

/** 一個月、一年各幾週。搜尋結果的發佈時間常常是幾個月、幾年前（M3 票 14）：「50 週前」沒有人算得出來。 */
const WEEKS_PER_MONTH = 30 / 7
const WEEKS_PER_YEAR = 365 / 7

/** `Intl.RelativeTimeFormat` 認得 `zh-Hant` 與 `en`，所以相對時間不必自己翻譯。 */
export function relative(moment: Date, language: string, now: number = Date.now()): string {
  const format = new Intl.RelativeTimeFormat(language, { numeric: 'auto' })
  let value = (moment.getTime() - now) / 1000

  for (const [unit, span] of UNITS) {
    if (Math.abs(value) < span) return format.format(Math.round(value), unit)
    value /= span
  }
  if (Math.abs(value) < WEEKS_PER_MONTH) return format.format(Math.round(value), 'week')
  // 先數月再看夠不夠一年：50 週捨入成 12 個月的話，說「一年」比說「12 個月」好讀。
  const months = Math.round(value / WEEKS_PER_MONTH)
  if (Math.abs(months) < 12) return format.format(months, 'month')
  return format.format(Math.round(value / WEEKS_PER_YEAR) || Math.sign(value), 'year')
}
