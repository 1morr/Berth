import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'
import type { Schemas } from './schemas'

/** 一次搜尋的整份回應（`berth/api/search.py` 的 `SearchOut`）。 */
export type SearchResults = Schemas['SearchOut']

/** 結果表的一列（`CONTEXT.md` 的 Search Result）。 */
export type SearchResult = Schemas['SearchResultOut']

/** 會進檔名的那幾格（brief §6.8）。 */
export type Tags = Schemas['TagsOut']

/** 索引站那邊沒搜到東西的五種樣子。與 `TmdbProblem` 一樣，五種的下一步都不同。 */
export type IndexerProblem = NonNullable<Schemas['IndexerProblem']>

/**
 * 索引站搜尋。**這一支很慢**——實測 35–85 秒，因為 Prowlarr 收到請求之後要現場去連它認得的
 * 每一個追蹤站。所以它是使用者按下去才發生的事（`useMutation`），不是進頁面就跑的查詢。
 */
export async function searchTorrents({
  media,
  q = '',
  route = null,
}: {
  media: string
  q?: string
  /** 這一輪搜尋的偏好，不是承諾（票 04b）：它只決定 anime profile 的查詢變體。 */
  route?: number | null
}) {
  const params = new URLSearchParams({ media })
  if (q) params.set('q', q)
  if (route !== null) params.set('route', String(route))
  return apiGet<SearchResults>(`/search?${params}`)
}

/**
 * 按下搜尋之前會送出去的那幾個關鍵字（`GET /api/search/queries`）。
 *
 * 不打索引站，只讀快照，所以改 Route 時隨手重問也很便宜——而那正是它的用處：
 * 選了動漫 Route 之後多出來的 `第N季` / `Season N` 變體要看得見。
 */
export function queriesQueryOptions(media: string, route: number | null) {
  const params = new URLSearchParams({ media })
  if (route !== null) params.set('route', String(route))

  return queryOptions({
    queryKey: ['search', 'queries', media, route],
    queryFn: () => apiGet<Schemas['SearchQueriesOut']>(`/search/queries?${params}`),
    staleTime: 5 * 60 * 1000,
  })
}
