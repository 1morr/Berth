import type { Media } from '../api/media'
import type { SearchResult, SearchResults } from '../api/search'
import type { Schemas } from '../api/schemas'
import { sortRows, type SortKey } from './searchResult'

/**
 * 搜尋結果的篩選按鈕與分組（M4 票 83，`.scratch/m4/search-filter-shape.md`）。
 *
 * 純函式、沒有 JSX：按鈕上的數字、表格的分組、每一組的上限說明要說同一件事。
 */

/** 一筆歸到的那一類（`berth/domain/enums.py` 的 `SearchVerdict`）。 */
export type Verdict = Schemas['SearchVerdict']

/** 有按鈕的那幾類。`unjudged`（自己打的關鍵字）不分類、沒有按鈕。 */
export type FilterVerdict = Exclude<Verdict, 'unjudged'>

/**
 * 按鈕的順序，也是表格分組的順序：「符合」永遠在第一格、最上面，不然 The Pirate Bay 熱門清單的
 * 五千個做種會壓在真正的結果上面（使用者確認 shape）。與後端列舉的順序相同。
 */
export const VERDICTS: readonly FilterVerdict[] = [
  'fits',
  'year',
  'not_movie',
  'adult',
  'partial_title',
  'unrelated',
]

/** 預設只開「符合」：其他類是 Berth 判斷不像這部作品的，按了才一起列出。 */
export const DEFAULT_OPEN: ReadonlySet<Verdict> = new Set<Verdict>(['fits'])

/** 這一次搜尋有沒有分類。自己打的關鍵字沒有（票 08），那時整張表一組、沒有按鈕。 */
export function isJudged(results: Pick<SearchResults, 'counts'>): boolean {
  return results.counts.some((count) => count.verdict !== 'unjudged')
}

/**
 * 預設就列出來、列上不標的那一份：分類時是「符合」，沒分類時是全部。與後端的 `_LISTED` 同一件事
 * （那兩類送 `RESULT_LIMIT` 筆）。
 */
export function isListed(verdict: Verdict): verdict is 'fits' | 'unjudged' {
  return verdict === 'fits' || verdict === 'unjudged'
}

/** 預設列出的那一份的總數。標頭與 `aria-live` 說的是它。 */
export function listedTotal(results: Pick<SearchResults, 'counts'>): number {
  return results.counts
    .filter((count) => isListed(count.verdict))
    .reduce((sum, count) => sum + count.total, 0)
}

/** 有東西的站，照後端第一次報它的順序。站別的下拉選單列的就是這幾個。 */
export function sitesOf(results: Pick<SearchResults, 'counts'>): string[] {
  return [...new Set(results.counts.map((count) => count.indexer))]
}

/**
 * 每一類的總筆數；`site` 有值時只算那一站。是總數不是送來的筆數——按鈕要說的是索引站回了多少，
 * 而送來的只是每類逐站輪流取的前幾筆。
 */
export function tallies(
  results: Pick<SearchResults, 'counts'>,
  site: string | null,
): Record<Verdict, number> {
  const totals = Object.fromEntries(
    [...VERDICTS, 'unjudged'].map((verdict) => [verdict, 0]),
  ) as Record<Verdict, number>
  for (const count of results.counts) {
    if (site === null || count.indexer === site) totals[count.verdict] += count.total
  }
  return totals
}

/** 表格的一組：一類，送來的那幾列（照排序鍵排好），與那一類的總數。 */
export interface Group {
  verdict: Verdict
  rows: SearchResult[]
  total: number
}

/**
 * 要畫的那幾組：開著的類，照 `VERDICTS` 的順序，總數是 0 的不畫。沒分類時整份一組。
 * `site` 有值時列與總數都只算那一站。
 */
export function groups(
  results: Pick<SearchResults, 'counts' | 'rows'>,
  open: ReadonlySet<Verdict>,
  site: string | null,
  sort: SortKey,
): Group[] {
  const totals = tallies(results, site)
  const shown: readonly Verdict[] = isJudged(results)
    ? VERDICTS.filter((verdict) => open.has(verdict))
    : ['unjudged']
  return shown
    .map((verdict) => ({
      verdict,
      rows: sortRows(
        results.rows.filter(
          (row) => row.verdict === verdict && (site === null || row.indexer === site),
        ),
        sort,
      ),
      total: totals[verdict],
    }))
    .filter((group) => group.total > 0)
}

/** 理由那一句的 key。是字面聯集而不是 `string`：拼錯一個在 `tsc` 就會紅。色塊上的類別名是 `labelKey`。 */
export type ReasonKey =
  | 'search.reason.year'
  | 'search.reason.yearShow'
  | 'search.reason.not_movie'
  | 'search.reason.adult'
  | 'search.reason.partial_title'
  | 'search.reason.unrelated'

/**
 * 不是「符合」的列底下那一句話：為什麼歸到這一類。證據（`evidence`）是發佈名裡的那一段字，原樣引用、
 * 不翻。符合與沒分類的列沒有這一句（The Usual Stays Unpainted Rule）。
 *
 * 年份那一句對電影說出這部作品是哪一年；劇集的年份是一段播出期間，前端不知道最後一季是哪一年，
 * 所以只說「不在播出期間」。`year` 一律帶著（只有年份那一句讀它）：i18next 的型別要每一個 key 的參數齊全。
 */
export function reasonOf(
  row: Pick<SearchResult, 'verdict' | 'evidence'>,
  media: Pick<Media, 'kind' | 'year'>,
): {
  labelKey: `search.verdict.${FilterVerdict}`
  key: ReasonKey
  evidence: string
  year: number
} | null {
  const verdict = row.verdict
  if (isListed(verdict)) return null
  const said = { labelKey: `search.verdict.${verdict}` as const, evidence: row.evidence }
  const year = media.year ?? 0
  if (verdict !== 'year') return { ...said, key: `search.reason.${verdict}`, year }
  return media.kind === 'movie' && media.year !== null
    ? { ...said, key: 'search.reason.year', year }
    : { ...said, key: 'search.reason.yearShow', year }
}
