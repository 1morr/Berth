import type { JobRefusal } from '../api/jobs'
import type { OneshotItem } from '../api/rss'

/**
 * 一次性 RSS 連結的那一批（票 18）：勾了哪幾筆、照什麼順序送、送完各自怎樣。純函式，元件只管畫。
 */

/** 一筆送單的結果。`refused` 是 `POST /jobs` 說不行（理由照 `jobs.refusal.*` 說）。 */
export type Outcome =
  | { kind: 'sent' | 'already'; hash: string }
  | { kind: 'refused'; reason: JobRefusal; detail: string }

/**
 * 勾選的那幾筆，**舊的先送**：feed 是新的在前，照 feed 的反序送，第 1 集先於第 2 集進 qBittorrent
 * （RSS 的 `_record` 同一個規矩）。
 */
export function sendOrder(
  items: readonly OneshotItem[],
  picked: ReadonlySet<string>,
): OneshotItem[] {
  return items.filter((item) => picked.has(item.guid)).reverse()
}

/**
 * 「勾選全部單集」勾的那幾筆：單集、還沒有下載、帳本也沒有的。合集與區間不在裡面——同一季的單集與
 * 合集一起勾就是下載兩次，要合集的人自己勾那一筆。
 */
export function freshSingles(items: readonly OneshotItem[]): Set<string> {
  return new Set(
    items
      .filter((item) => item.release_kind === 'single' && !item.job_hash && item.known === null)
      .map((item) => item.guid),
  )
}

/** 送完之後那一句：幾筆送出、幾筆本來就在了、幾筆沒送出。 */
export function tally(outcomes: ReadonlyMap<string, Outcome>) {
  const counts = { sent: 0, already: 0, refused: 0 }
  for (const outcome of outcomes.values()) counts[outcome.kind] += 1
  return counts
}
