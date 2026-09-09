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

/**
 * 追蹤這部作品並指定預設 Route。**`folder_name` 在這一刻凍結**（plan §5）。
 *
 * 重按只是改 Route——後端那一支是同一個命令，Route 不在凍結之列。
 */
export async function track(id: string, routeId: number | null) {
  const body = { route_id: routeId } satisfies Schemas['TrackIn']
  return apiPost<Media>(`/media/${encodeURIComponent(id)}/track`, body)
}

/** 立刻重抓快照。凍結過的資料夾名不會被動到。 */
export async function refresh(id: string) {
  return apiPost<Media>(`/media/${encodeURIComponent(id)}/refresh`)
}
