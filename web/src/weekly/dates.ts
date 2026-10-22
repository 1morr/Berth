/** `2026-10-19 – 10-25`：同一年只寫一次年份。日期是容器時區的週一到週日，畫面只寫日期。 */
export function dayRange(first: string, last: string): string {
  return first.slice(0, 4) === last.slice(0, 4)
    ? `${first} – ${last.slice(5)}`
    : `${first} – ${last}`
}

/** `10-26 05:00`，瀏覽器的當地時間。 */
export function monthDayTime(moment: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(moment.getMonth() + 1)}-${pad(moment.getDate())} ${pad(moment.getHours())}:${pad(moment.getMinutes())}`
}
