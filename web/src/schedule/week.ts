/**
 * 時間表的日期（M5.5 票 09）。後端送的是 `YYYY-MM-DD`（伺服器時區的日期，沒有時刻）。
 */

/** `start`（週一）起的七天。 */
export function weekDays(start: string): string[] {
  const first = localDate(start)
  return Array.from({ length: 7 }, (_, offset) => {
    const day = new Date(first.getFullYear(), first.getMonth(), first.getDate() + offset)
    return isoDate(day)
  })
}

/** `2026-11-03` → 那一天的本地午夜。不能 `new Date(iso)`：那是 UTC 午夜，西半球會變成前一天。 */
function localDate(iso: string): Date {
  const [year = 1970, month = 1, day = 1] = iso.split('-').map(Number)
  return new Date(year, month - 1, day)
}

function isoDate(day: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${String(day.getFullYear())}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`
}

/** 「11/3」「週二」這種寫法，照 UI 語言。 */
export function monthDay(iso: string, language: string): string {
  return localDate(iso).toLocaleDateString(language, { month: 'numeric', day: 'numeric' })
}

export function weekday(iso: string, language: string, form: 'short' | 'long'): string {
  return localDate(iso).toLocaleDateString(language, { weekday: form })
}

/**
 * 放送時刻（M5.5 票 14）：照瀏覽器的時區寫「23:00」。本地日期不是卡片那一天時前面寫星期
 * （「週六 00:30」）：卡片放在 TMDB 的播出日，深夜檔與時差會讓那一刻落在隔天。
 *
 * `timeZone` 只給測試用；畫面上不給，就是瀏覽器的時區。
 */
export function airingTime(at: string, day: string, language: string, timeZone?: string): string {
  const instant = new Date(at)
  const time = instant.toLocaleTimeString(language, {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone,
  })
  // `en-CA` 的日期就是 `YYYY-MM-DD`，與卡片的 `air_date` 直接比。
  const localDay = instant.toLocaleDateString('en-CA', { timeZone })
  if (localDay === day) return time
  return `${instant.toLocaleDateString(language, { weekday: 'short', timeZone })} ${time}`
}
