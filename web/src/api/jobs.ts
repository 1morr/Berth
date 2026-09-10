import { queryOptions } from '@tanstack/react-query'

import { ApiError, apiGet, apiPost } from './client'
import type { Schemas } from './schemas'

/** 下載列表與時間線上的一筆（`berth/api/jobs.py` 的 `JobOut`）。 */
export type Job = Schemas['JobOut']

/** Job 的十六個狀態（plan §3.1）。M1 票 09 只走得到前三個。 */
export type JobState = Job['state']

/** 時間線上的一筆事件（brief §5.2）。 */
export type JobEvent = Schemas['JobEventOut']

/** 送單的 body。`route` 是必填——猜一條的代價是檔案進錯媒體庫。 */
export type JobCreate = Schemas['JobCreateIn']

/**
 * 送單被擋下來的理由（`berth/api/jobs.py` 的 `_STATUS`）。
 *
 * 是字面聯集而不是 `string`：每一種都有自己的一句話與下一步（PRODUCT 原則 4），
 * 而少寫一種在 `tsc` 就會紅，不會變成畫面上一句空白。
 */
export type JobRefusal =
  | 'media_missing'
  | 'route_missing'
  | 'route_kind_mismatch'
  | 'route_disabled'
  | 'route_unhealthy'
  | 'source_unavailable'
  | 'job_missing'
  | 'not_retryable'

/** 拒絕的完整形狀：一個封閉集合的理由，加上服務回的原文。 */
export interface JobRefusalDetail {
  reason: JobRefusal
  detail: string
}

const REASONS: readonly JobRefusal[] = [
  'media_missing',
  'route_missing',
  'route_kind_mismatch',
  'route_disabled',
  'route_unhealthy',
  'source_unavailable',
  'job_missing',
  'not_retryable',
]

/**
 * 這一次失敗是「後端說不行」還是「網路壞了」。
 *
 * 認不得的理由回 `null`，畫面落回一句通用的話——後端加了新的理由而前端還沒跟上時，
 * 使用者該看到的是一句誠實的通用訊息，不是一條 i18n key。
 */
export function refusalOf(error: unknown): JobRefusalDetail | null {
  if (!(error instanceof ApiError)) return null
  const detail = error.detail
  if (typeof detail !== 'object' || detail === null) return null
  const reason = (detail as { reason?: unknown }).reason
  if (typeof reason !== 'string' || !REASONS.includes(reason as JobRefusal)) return null
  const text = (detail as { detail?: unknown }).detail
  return { reason: reason as JobRefusal, detail: typeof text === 'string' ? text : '' }
}

/**
 * 下載列表。**這一票不輪詢**：M1 票 09 的狀態只在使用者按下送單或重試時才會變，
 * 而真的會自己跑的進度要等票 10 的 poller 與 SSE（plan §3.2、§6 events 群組）。
 */
export function jobsQueryOptions() {
  return queryOptions({
    queryKey: ['jobs'],
    queryFn: () => apiGet<Job[]>('/jobs'),
  })
}

/** 一筆 Job 的時間線，最舊在前。列展開時才問——一份清單裡多數列不會被展開。 */
export function jobEventsQueryOptions(hash: string, enabled: boolean) {
  return queryOptions({
    queryKey: ['jobs', hash, 'events'],
    queryFn: () => apiGet<JobEvent[]>(`/jobs/${encodeURIComponent(hash)}/events`),
    enabled,
  })
}

/**
 * 送一個 torrent 進 qBittorrent。
 *
 * **qBittorrent 收不下不會丟例外**：那時 Job 已經建好了，回來的是一筆 `submit_failed`
 * 加上原文（plan §3.1）。丟例外的是「在建 Job 之前就擋下來」的那幾種——紅的 Route、
 * 收不下這種作品的 Route、索引站給不出那份 torrent。
 */
export async function submitJob(body: JobCreate) {
  return apiPost<Schemas['JobCreatedOut']>('/jobs', body satisfies Schemas['JobCreateIn'])
}

/** `submit_failed` → `requested` → 再送一次（plan §3.1）。 */
export async function retryJob(hash: string) {
  return apiPost<Job>(`/jobs/${encodeURIComponent(hash)}/retry`)
}
