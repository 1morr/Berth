import { queryOptions } from '@tanstack/react-query'

import { apiDelete, apiGet, apiPost, apiPut } from './client'
import { parseRefusal, type ReasonSet } from './refusal'
import type { Schemas } from './schemas'

/** 一個 Feed（`berth/api/rss.py` 的 `FeedOut`）。 */
export type Feed = Schemas['FeedOut']

/** 一個 RSS Series。`media_id` 是 `null` 就是待綁定。 */
export type RssSeries = Schemas['SeriesOut']

/** 自動綁定的一條理由（`domain.BindReason`，票 09）：code 加不翻譯的參數。 */
export type BindReason = Schemas['BindReasonOut']

/** `domain.BindReasonCode`。 */
export type BindReasonCode = Schemas['BindReasonCode']

/** 待綁定那一列給人一鍵選的作品。 */
export type Candidate = Schemas['CandidateOut']

/** 一筆 Feed Item。 */
export type FeedItem = Schemas['ItemOut']

/** 一筆 Item 為什麼沒送出去（`domain.SkipReason`，票 10）：code 加不翻譯的參數。 */
export type SkipReason = Schemas['SkipReasonOut']

/** `domain.SkipCode`。 */
export type SkipCode = Schemas['SkipCode']

/** 全域那一層的排除條件（`settings.rss`）。 */
export type Exclusions = Schemas['ExclusionsOut']

/** 一輪輪詢的結果。 */
export type PollOutcome = Schemas['PollOut']

/** 新 Feed 第一輪選了哪一個（票 11）。 */
export type PrimeMode = Schemas['PrimeMode']

/** 選完第一輪的結果。 */
export type PrimeOutcome = Schemas['PrimeOut']

/** 一次性 RSS 連結讀到的那一份（票 18）。 */
export type Oneshot = Schemas['OneshotOut']

/** 一次性 RSS 連結的一筆：送單要的那幾格，加上解析結果與「已經有了」。 */
export type OneshotItem = Schemas['OneshotItemOut']

/** `berth/domain/enums.py` 的 `RssRefusal`。 */
export type RssRefusal = Schemas['RssRefusal']

/** 執行期認得的那幾種。**少一種或多一種都是編譯錯誤**（同 `api/issues.ts`）。 */
const REASONS: ReasonSet<RssRefusal> = {
  feed_missing: true,
  feed_unsupported: true,
  feed_duplicate: true,
  series_missing: true,
  series_bound: true,
  media_missing: true,
  route_missing: true,
  route_disabled: true,
  route_kind_mismatch: true,
  rule_invalid: true,
  feed_primed: true,
  feed_unreachable: true,
  feed_unread: true,
  feed_not_rss: true,
}

export function parseRssRefusal(error: unknown) {
  return parseRefusal(error, REASONS)
}

/** `/rss` 上三份清單共用的前綴：一個動作之後三份一起重問（綁定會改 Series 也會改 Item）。 */
export const RSS_KEY = ['rss'] as const

/** 一次性 RSS 連結（`oneshotQueryOptions`）。`queryKey[1]` 是網址。 */
export const ONESHOT_KEY = ['rss-oneshot'] as const

export function exclusionsQueryOptions() {
  return queryOptions({
    queryKey: [...RSS_KEY, 'exclusions'],
    queryFn: () => apiGet<Exclusions>('/rss/exclusions'),
  })
}

export function feedsQueryOptions() {
  return queryOptions({
    queryKey: [...RSS_KEY, 'feeds'],
    queryFn: () => apiGet<Feed[]>('/rss/feeds'),
  })
}

export function seriesQueryOptions() {
  return queryOptions({
    queryKey: [...RSS_KEY, 'series'],
    queryFn: () => apiGet<RssSeries[]>('/rss/series'),
  })
}

export function itemsQueryOptions() {
  return queryOptions({
    queryKey: [...RSS_KEY, 'items'],
    queryFn: () => apiGet<FeedItem[]>('/rss/items'),
  })
}

/** 還沒選第一輪的 Feed 的每一筆，說出各自會怎樣（票 11）。 */
export function previewQueryOptions(id: number) {
  return queryOptions({
    queryKey: [...RSS_KEY, 'preview', id],
    queryFn: () => apiGet<FeedItem[]>(`/rss/feeds/${id}/preview`),
  })
}

/**
 * 讀一次那一條網址（票 18）。**只讀**：不建 Feed；勾好的那幾筆走一般的 `POST /jobs`。
 *
 * 是查詢不是 mutation：選了作品與 Route 之後換成照它們算的季集與「帳本已有」，送單之後 `ONESHOT_KEY`
 * 失效時重讀一次、說出哪幾筆已經有下載了。**不重試、不自己重抓**：讀不到是上游的答案（502 帶原文），
 * 換頁回來就再打一次 Mikan 也沒有意義。網址放在 body（聚合 feed 的網址帶 token）。
 *
 * **不在 `RSS_KEY` 底下**：頁上其他區塊的動作（輪詢、存排除條件、綁定）都讓 `RSS_KEY` 整個失效，掛在
 * 底下的話每按一次就重打一次上游。
 */
export function oneshotQueryOptions(url: string, media: string | null, route: number | null) {
  return queryOptions({
    queryKey: [...ONESHOT_KEY, url, media, route],
    queryFn: () => apiPost<Oneshot>('/rss/oneshot', { url, media, route }),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  })
}

export function primeFeed(id: number, mode: PrimeMode) {
  return apiPost<PrimeOutcome>(`/rss/feeds/${id}/prime`, { mode })
}

export function addFeed(url: string, name: string) {
  return apiPost<Feed>('/rss/feeds', { url, name })
}

export function deleteFeed(id: number) {
  return apiDelete<{ items: number }>(`/rss/feeds/${id}`)
}

export function pollFeed(id: number) {
  return apiPost<PollOutcome>(`/rss/feeds/${id}/poll`)
}

/** `backfill` 只對 Mikan 的 RSS Series 有作用（票 12）：讀單一 feed 補舊集；`false` 時舊集記成略過。 */
export function bindSeries(id: number, media: string, route: number, backfill: boolean) {
  return apiPut<RssSeries>(`/rss/series/${id}/binding`, { media, route, backfill })
}

export function unbindSeries(id: number) {
  return apiDelete<RssSeries>(`/rss/series/${id}/binding`)
}

/** 三層的排除條件都是整組覆寫；寫壞的那一條讓整組不存（422 `rule_invalid`）。 */
export function saveExclusions(notSingle: boolean, rules: string[]) {
  return apiPut<Exclusions>('/rss/exclusions', { not_single: notSingle, rules })
}

export function saveFeedExclusions(id: number, rules: string[]) {
  return apiPut<Feed>(`/rss/feeds/${id}/exclusions`, { rules })
}

export function saveSeriesExclusions(id: number, rules: string[]) {
  return apiPut<RssSeries>(`/rss/series/${id}/exclusions`, { rules })
}
