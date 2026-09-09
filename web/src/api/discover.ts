import { queryOptions } from '@tanstack/react-query'

import { apiGet } from './client'
import type { Schemas } from './schemas'

/** 牆上的一格。 */
export type DiscoverItem = Schemas['DiscoverItemOut']

/** 一個 feed 的回應。**失敗也是 200**，理由在後端的 `DiscoverOut`。 */
export type Discover = Schemas['DiscoverOut']

/** 拿不到 TMDB 的三種樣子。每一種的下一步不同（`berth/domain/enums.py`）。 */
export type DiscoverProblem = NonNullable<Schemas['DiscoverProblem']>

/** 少於這個字數不發搜尋：一兩個字的結果沒有意義，卻要花掉使用者自備的 TMDB 額度。 */
export const MIN_QUERY_LENGTH = 2

/**
 * 後端已經快取一小時，所以前端這一層只為了「切回分頁不要每次都重抓」。
 * 重抓本身只讀資料庫、不打 TMDB，但畫面會閃一下。
 */
const STALE_TIME = 5 * 60 * 1000

export const trendingQueryOptions = queryOptions({
  queryKey: ['discover', 'trending'],
  queryFn: () => apiGet<Discover>('/discover/trending'),
  staleTime: STALE_TIME,
})

export const popularQueryOptions = queryOptions({
  queryKey: ['discover', 'popular'],
  queryFn: () => apiGet<Discover>('/discover/popular'),
  staleTime: STALE_TIME,
})

/** 查詢字串是 query key 的一部分，所以每一輪搜尋各自快取，回頭再打同一個詞是即時的。 */
export function searchQueryOptions(query: string) {
  return queryOptions({
    queryKey: ['discover', 'search', query],
    queryFn: () => apiGet<Discover>(`/discover/search?q=${encodeURIComponent(query)}`),
    enabled: query.length >= MIN_QUERY_LENGTH,
    staleTime: STALE_TIME,
  })
}
