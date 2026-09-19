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
  missing = null,
}: {
  media: string
  q?: string
  missing?: MissingScope | null
}) {
  const params = new URLSearchParams({ media })
  if (q) params.set('q', q)
  return apiGet<SearchResults>(`/search?${missingParams(params, missing)}`)
}

/**
 * 從季表的缺集開始搜（M1.5 票 10）：`season` 是 `null` 時整部作品，有值時只有那一季。
 *
 * 查詢長什麼樣子**由後端決定**——這裡送的是範圍，不是關鍵字。
 */
export interface MissingScope {
  season: number | null
}

function missingParams(params: URLSearchParams, missing: MissingScope | null) {
  if (missing) {
    params.set('missing', 'true')
    if (missing.season !== null) params.set('season', String(missing.season))
  }
  return params
}

/**
 * 按下搜尋之前會送出去的那幾個關鍵字（`GET /api/search/queries`）。不打索引站，只讀快照。
 *
 * 規則在後端一份（`search_titles`）：第二季以後多出來的 `第N季` / `Season N` 變體要看得見，
 * 而前端重算一份遲早會與真的搜尋長出不同的答案。
 */
export function queriesQueryOptions(media: string, missing: MissingScope | null = null) {
  const params = missingParams(new URLSearchParams({ media }), missing)

  return queryOptions({
    queryKey: ['search', 'queries', media, missing ? (missing.season ?? 'all') : 'titles'],
    queryFn: () => apiGet<Schemas['SearchQueriesOut']>(`/search/queries?${params}`),
    staleTime: 5 * 60 * 1000,
  })
}
