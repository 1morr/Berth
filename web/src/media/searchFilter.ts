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

/**
 * 照作品名搜的那幾類。按鈕的順序，也是表格分組的順序：「符合」永遠在第一格、最上面，不然
 * The Pirate Bay 熱門清單的五千個做種會壓在真正的結果上面（使用者確認 shape）。與後端列舉的順序相同。
 */
const VERDICTS: readonly [Verdict, ...Verdict[]] = [
  'fits',
  'year',
  'not_movie',
  'adult',
  'partial_title',
  'unrelated',
]

/**
 * 自己打關鍵字時的兩類（M4 票 83b，`.scratch/m4/search-typed-filter-shape.md`）：只判發佈名對不對得上
 * 打的字（或這部作品的某個名字），不判是不是這部作品（票 08）。與上面那幾類不會出現在同一次搜尋。
 */
const TYPED_VERDICTS: readonly [Verdict, ...Verdict[]] = ['typed_match', 'typed_miss']

/**
 * 這一次搜尋有哪幾類：照作品名搜是六類，自己打關鍵字是兩類。第一類永遠有按鈕，也是預設唯一開著的：
 * 其他類是 Berth 判斷不像要找的東西，按了才一起列出。
 */
export function verdictsOf(typed: string): readonly [Verdict, ...Verdict[]] {
  return typed ? TYPED_VERDICTS : VERDICTS
}

/**
 * 預設就列出來、列上不標的那一份：照作品名搜是「符合」，自己打字是「對得上」。與後端的 `_LISTED`
 * 同一件事（那兩類送 `RESULT_LIMIT` 筆）。
 */
function isListed(verdict: Verdict): verdict is 'fits' | 'typed_match' {
  return verdict === 'fits' || verdict === 'typed_match'
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
    [...VERDICTS, ...TYPED_VERDICTS].map((verdict) => [verdict, 0]),
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
 * 要畫的那幾組：`verdicts`（`verdictsOf`）裡開著的類，照它的順序，總數是 0 的不畫。
 * `site` 有值時列與總數都只算那一站。
 */
export function groups(
  results: Pick<SearchResults, 'counts' | 'rows'>,
  verdicts: readonly Verdict[],
  open: ReadonlySet<Verdict>,
  site: string | null,
  sort: SortKey,
): Group[] {
  const totals = tallies(results, site)
  return verdicts
    .filter((verdict) => open.has(verdict))
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
  | 'search.reason.typed_miss'

/**
 * 不是預設列出那一類的列底下那一句話：為什麼歸到這一類。證據（`evidence`）是發佈名裡的那一段字，原樣引用、
 * 不翻。「符合」與「對得上」的列沒有這一句（The Usual Stays Unpainted Rule）。
 *
 * 「對不上」的證據是打的那串字（`typed`，這一次送出去的那一個）：它不在發佈名裡，後端不送。
 *
 * 年份那一句對電影說出這部作品是哪一年；劇集的年份是一段播出期間，前端不知道最後一季是哪一年，
 * 所以只說「不在播出期間」。`year` 一律帶著（只有年份那一句讀它）：i18next 的型別要每一個 key 的參數齊全。
 */
export function reasonOf(
  row: Pick<SearchResult, 'verdict' | 'evidence'>,
  media: Pick<Media, 'kind' | 'year'>,
  typed: string,
): {
  labelKey: `search.verdict.${Verdict}`
  key: ReasonKey
  evidence: string
  year: number
} | null {
  const verdict = row.verdict
  if (isListed(verdict)) return null
  const labelKey = `search.verdict.${verdict}` as const
  const year = media.year ?? 0
  if (verdict === 'typed_miss')
    return { labelKey, key: 'search.reason.typed_miss', evidence: typed, year }
  const said = { labelKey, evidence: row.evidence }
  if (verdict !== 'year') return { ...said, key: `search.reason.${verdict}`, year }
  return media.kind === 'movie' && media.year !== null
    ? { ...said, key: 'search.reason.year', year }
    : { ...said, key: 'search.reason.yearShow', year }
}
