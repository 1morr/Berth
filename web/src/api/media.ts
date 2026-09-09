import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type { Schemas } from './schemas'

/** 詳情頁的一整份（`berth/api/media.py` 的 `MediaOut`）。 */
export type Media = Schemas['MediaOut']

/** 一季。`season_number: 0` 是 Specials。 */
export type Season = Schemas['SeasonOut']

/** 一集。 */
export type Episode = Schemas['EpisodeOut']

/** 下拉裡的一條 Route。後端只回 `collection_type` 相符的那幾條。 */
export type RouteChoice = Schemas['RouteChoiceOut']

/**
 * 後端已經照 24 小時的規則管快照（plan §8.3），所以前端這一層只為了「切回分頁不要重抓」。
 * 重抓本身多半只讀資料庫、不打 TMDB，但畫面會閃一下。
 */
const STALE_TIME = 5 * 60 * 1000

export function mediaQueryOptions(id: string) {
  return queryOptions({
    queryKey: ['media', id],
    queryFn: () => apiGet<Media>(`/media/${encodeURIComponent(id)}`),
    staleTime: STALE_TIME,
  })
}

/** 立刻重抓快照。TMDB 改了標題，「將會是」的那一串字就跟著改（票 04b）。 */
export async function refresh(id: string) {
  return apiPost<Media>(`/media/${encodeURIComponent(id)}/refresh`)
}
