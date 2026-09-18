import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import { retryUnlessRefused } from './jellyfin'
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

/**
 * 觀看區（`berth/api/media.py` 的 `WatchAreaOut`、M1.5 票 08）：作品在 Jellyfin 裡、這個人看得到時才有，
 * 否則是 `null`——不在與看不到是同一個答案。前端不送任何使用者 id。
 */
export type WatchArea = Schemas['WatchAreaOut']

/** 觀看區的一集：選季選集的一格，也是主按鈕那一集。 */
export type WatchEpisode = Schemas['WatchEpisodeOut']

/** Jellyfin 的一季（不是 TMDB 的 `Season`）。 */
export type WatchSeason = Schemas['WatchSeasonOut']

/**
 * 快取鍵**不在 `['media', id]` 底下**：重抓 TMDB 快照（`refresh`）換掉的是那一份，觀看區是 Jellyfin 的另一份。
 * 說得出理由的拒絕不重試（Jellyfin 問不到、帳號被停用）。
 */
export function watchKey(id: string) {
  return ['watch', id] as const
}

export function watchQueryOptions(id: string) {
  return queryOptions({
    queryKey: watchKey(id),
    queryFn: () => apiGet<WatchArea | null>(`/media/${encodeURIComponent(id)}/watch`),
    retry: retryUnlessRefused,
  })
}

export function episodesKey(seriesId: string, seasonId: string) {
  return ['episodes', seriesId, seasonId] as const
}

/**
 * 一季的集。**換季時先留著上一季**（`placeholderData`）：沒有的話整格換成空位，焦點掉回 `body`
 * （媒體庫牆換頁的同一個理由，票 06）。換到別部劇時不留。
 */
export function episodesQueryOptions(seriesId: string, seasonId: string) {
  const search = new URLSearchParams({ season_id: seasonId })
  return queryOptions({
    queryKey: episodesKey(seriesId, seasonId),
    queryFn: () =>
      apiGet<WatchEpisode[]>(`/jellyfin/shows/${encodeURIComponent(seriesId)}/episodes?${search}`),
    retry: retryUnlessRefused,
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === seriesId ? previous : undefined,
  })
}
