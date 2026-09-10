import type { SearchResult } from '../api/search'

/**
 * 結果表那幾格的讀法（`.scratch/m1/search-results-shape.md` §6）。
 *
 * 純函式、沒有 JSX：三個地方（桌機表格、窄版堆疊列、`aria-live` 的宣告）要說同一件事，
 * 而同一件事在三個元件裡各算一次遲早會分岔。
 */

/** 排序依據。欄頭與窄版的下拉改的是同一個值。 */
export type SortKey = 'seeders' | 'size'

/**
 * 預估那一格要翻譯的那個詞。是字面聯集而不是 `string`：i18next 的 key 有型別，
 * 拼錯一個在 `tsc` 就會紅，而不是在畫面上印出一條 key。
 */
export type EstimateNote =
  '' | 'search.estimate.wholeSeason' | 'search.estimate.unknown' | 'search.estimate.movie'

/**
 * 位元組 → `4.8 GB` / `500 MB`。索引站沒說大小時是 `—`。
 *
 * 單位用 SI 符號不走 i18n：`MB` 在兩個語言都是 `MB`，而數字本身照 locale 分節。
 * 一律 1024 進位——torrent 客戶端全都這樣算，Berth 說的數字要跟 qBittorrent 對得起來。
 */
export function formatSize(bytes: number, locale: string): string {
  if (!bytes) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit += 1
  }
  const digits = value < 10 && unit > 1 ? 1 : 0
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value)} ${units[unit]}`
}

/**
 * 做種數。`null` 是「那個站沒報」，與 0（真的沒有人做種）不是同一件事，所以畫 `—`。
 */
export function formatCount(count: number | null, locale: string): string {
  return count === null ? '—' : new Intl.NumberFormat(locale).format(count)
}

/**
 * 預估季集的三種說法（票 08）：`S03 全季` / `S03E13` / 判斷不出來。
 *
 * `code` 是機器字串（`S03E13`，與季集清單同一個語域，不走 i18n、不走 `.label`）；
 * `noteKey` 是要翻譯的那一個詞。兩者都可能是空的——只有 `code` 是單集或區間，
 * 只有 `noteKey` 是電影或判斷不出來。
 */
export function estimate(row: SearchResult): { code: string; noteKey: EstimateNote } {
  if (row.strategy === 'movie') return { code: '', noteKey: 'search.estimate.movie' }
  if (row.season === null && row.episode_start === null) {
    return { code: '', noteKey: 'search.estimate.unknown' }
  }

  const season = row.season === null ? '' : `S${pad(row.season)}`
  if (row.whole_season) return { code: season, noteKey: 'search.estimate.wholeSeason' }
  if (row.episode_start === null) return { code: season, noteKey: '' }

  const start = `E${pad(row.episode_start)}`
  const end =
    row.episode_end === null || row.episode_end === row.episode_start
      ? ''
      : `–E${pad(row.episode_end)}`
  return { code: `${season}${start}${end}`, noteKey: '' }
}

/**
 * Tags 欄要畫的那幾塊色塊，順序照 brief §6.8 的檔名順序。
 *
 * 逐格畫而不是用後端的 `Tags.render()` 那一串字：欄位是結構化的，而使用者要一眼認出
 * 「這是 1080p」而不是讀一條 `[WEB][1080p][CHT][ANi]`。內容仍然與那一串字一致——
 * 詞彙表只有 brief §6.8 一份。
 */
export function tagTokens(tags: SearchResult['tags']): string[] {
  return [
    tags.source ?? '',
    tags.resolution,
    tags.subs.join('+'),
    tags.hardsub ? 'Hardsub' : '',
    tags.group,
    tags.version,
    tags.edition,
  ].filter(Boolean)
}

/** 依做種或大小由多到少。`null` 做種排在最後——「沒報」拿不出理由排前面。 */
export function sortRows(rows: readonly SearchResult[], key: SortKey): SearchResult[] {
  return [...rows].sort((left, right) => value(right, key) - value(left, key))
}

function value(row: SearchResult, key: SortKey): number {
  if (key === 'size') return row.size
  return row.seeders ?? -1
}

function pad(value: number): string {
  return String(value).padStart(2, '0')
}
