import { keepPreviousData, queryOptions } from '@tanstack/react-query'

import { ApiError, apiDelete, apiGet, apiPost } from './client'
import { parseRefusal, type ReasonSet } from './refusal'
import type { Schemas } from './schemas'

/** 下載列表與時間線上的一筆（`berth/api/jobs.py` 的 `JobOut`）。 */
export type Job = Schemas['JobOut']

/** 下載列表的一頁（`JobPageOut`，M4 票 04）：這一頁的 Job、這個篩選一共幾筆、四個篩選各幾筆。 */
export type JobPage = Schemas['JobPageOut']

/** 四個篩選（`domain/enums.py` 的 `JobFilter`）。`active` 是預設：在路上的。 */
export type JobFilter = Schemas['JobFilter']

/** 篩選鍵，照這裡的先後排。`ReasonSet` 是整個封閉集合的 `Record`：少一種或多一種都是編譯錯誤。 */
const FILTER_ORDER: ReasonSet<JobFilter> = {
  active: true,
  attention: true,
  imported: true,
  all: true,
}
export const JOB_FILTERS = Object.keys(FILTER_ORDER) as JobFilter[]

export function isJobFilter(value: unknown): value is JobFilter {
  return JOB_FILTERS.some((filter) => filter === value)
}

/** Job 的十六個狀態（plan §3.1）。M1 票 09 只走得到前三個。 */
export type JobState = Job['state']

/** 時間線上的一筆事件（brief §5.2）。 */
export type JobEvent = Schemas['JobEventOut']

/** 送單的 body。`route` 是必填——猜一條的代價是檔案進錯媒體庫。 */
export type JobCreate = Schemas['JobCreateIn']

/**
 * 送單被擋下來的理由（`berth/domain/enums.py` 的 `JobRefusal`）。
 *
 * 是封閉集合而不是 `string`：每一種都有自己的一句話與下一步（PRODUCT 原則 4），
 * 所以 `t(`jobs.refusal.${reason}`)` 少一句就是編譯錯誤，不會變成畫面上一條 i18n key。
 */
export type JobRefusal = Schemas['JobRefusal']

/** 拒絕的完整形狀：一個封閉集合的理由，加上服務回的原文。 */
export type JobRefusalDetail = Schemas['JobRefusalOut']

/**
 * 執行期認得的那幾種。型別會在編譯時抹掉，所以這一份表還是要在——但它是
 * `ReasonSet<JobRefusal>`，**少一種或多一種都是編譯錯誤**（M2 票 02）。
 */
const REASONS: ReasonSet<JobRefusal> = {
  media_missing: true,
  route_missing: true,
  route_kind_mismatch: true,
  route_disabled: true,
  route_unhealthy: true,
  source_unavailable: true,
  job_missing: true,
  not_retryable: true,
  not_replannable: true,
  client_unreachable: true,
  delete_files_requires_remove_torrent: true,
  not_reimportable: true,
  content_missing: true,
  moved_on: true,
  low_disk_space: true,
  job_removed: true,
  review_needs_admin: true,
}

/** 這一次失敗是「後端說不行」還是「網路壞了」。判定與另外兩組共用（`api/refusal.ts`）。 */
export function refusalOf(error: unknown): JobRefusalDetail | null {
  return parseRefusal(error, REASONS)
}

/** 下載列表每一頁共同的前綴。SSE 一批推播只讓它失效一次（`api/events.ts`）。 */
export const JOBS_LIST_KEY = ['jobs', 'list'] as const

/**
 * 下載列表的一頁（M4 票 04）。key 掛在 `JOBS_LIST_KEY` 底下，而 `['jobs']` 整個前綴仍涵蓋它——按完動作的
 * 那幾處照舊失效 `['jobs']`。
 *
 * **新的一頁回來之前留著上一頁**（翻頁與換篩選都是）：篩選列與件數不會閃掉。上一頁是哪一組看回應自己的
 * `filter`——換了篩選之後，舊那一組的列不能掛在新的篩選鍵底下畫出來（`JobsPage`）。
 */
export function jobsQueryOptions(filter: JobFilter, page: number) {
  return queryOptions({
    queryKey: [...JOBS_LIST_KEY, filter, page],
    queryFn: ({ signal }) => apiGet<JobPage>(`/jobs?filter=${filter}&page=${page}`, { signal }),
    placeholderData: keepPreviousData,
  })
}

/**
 * 一筆 Job（`/jobs/:hash`，M2 票 12）。**key 掛在 `['jobs', hash]`**：SSE 讓推播到的那一筆的前綴失效
 * （`api/events.ts`），所以詳情頁不必另外接一條訂閱就會跟著動。不存在的 hash 是 404——
 * 詳情頁拿它畫空狀態，而不是當成後端壞了。
 */
export function jobQueryOptions(hash: string) {
  return queryOptions({
    queryKey: ['jobs', hash],
    queryFn: ({ signal }) => apiGet<Job>(`/jobs/${encodeURIComponent(hash)}`, { signal }),
    // **後端回了狀態碼就是答案**，只有網路層失敗才重試：預設的三次重試、間隔加倍會讓不存在的 hash
    // 晚七秒才畫出空狀態（實跑量到）；同源的 Berth 回 5xx 是它自己的錯，重試只是晚七秒說。
    // 與 `api/jellyfin.ts` 的 `retryUnlessRefused` 同一個道理，但這裡的 404 不是 refusal 形狀。
    retry: (failures, error) => !(error instanceof ApiError) && failures < 3,
  })
}

/** 一筆 Job 的時間線，最舊在前。列展開時才問——一份清單裡多數列不會被展開。 */
export function jobEventsQueryOptions(hash: string, enabled: boolean) {
  return queryOptions({
    queryKey: ['jobs', hash, 'events'],
    queryFn: ({ signal }) =>
      apiGet<JobEvent[]>(`/jobs/${encodeURIComponent(hash)}/events`, { signal }),
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

/**
 * 以 complete 裡那一包重新入庫（CONTEXT.md 的 Reimport、brief §9.3、M2 票 10）。回的是退回
 * `completed` 的那一筆；規劃與鏈接是背景迴圈照常的一輪。只有 admin 按得到（門禁）。
 */
export async function reimportJob(hash: string) {
  return apiPost<Job>(`/jobs/${encodeURIComponent(hash)}/reimport`)
}

/**
 * 刪除範圍的四個旗標（brief §9.2）。**預設全不勾**——後端的 `DeleteScope` 是同一組預設，
 * 所以對話框沒送出去的那幾格與命令自己的預設是同一件事。
 */
export type DeleteScope = {
  unlink: boolean
  removeTorrent: boolean
  deleteFiles: boolean
  purge: boolean
}

/** 什麼都不勾。對話框開啟時的狀態，也是「只把這一筆從清單上收掉」那一種刪除。 */
export const NOTHING_TICKED: DeleteScope = {
  unlink: false,
  removeTorrent: false,
  deleteFiles: false,
  purge: false,
}

/** 刪下去會空出多少（`berth/api/jobs.py` 的 `DeletionEstimateOut`）。 */
export type DeletionEstimate = Schemas['DeletionEstimateOut']

/** 一次刪除真的做掉了什麼（`JobDeletedOut`）。 */
export type JobDeleted = Schemas['JobDeletedOut']

/**
 * 這一筆刪下去會空出多少。**逐一 `stat` 每一個來源與目標，所以它慢**（brief §9.2）——
 * 畫面在等它的時候要說「正在算」。
 *
 * 只在對話框打開時才問（`enabled`）：一份清單裡多數列不會被展開，而這一支會去摸磁碟。
 *
 * **key 不在 `['jobs']` 底下**（M4 票 04）：那個前綴會被 SSE 與每一個動作失效，而估算每重跑一次就
 * 逐檔 `stat` 一次。它只在對話框打開的那一刻算（`staleTime: 0`），不跟著任何一筆的進度重算。
 */
export function deletionQueryOptions(hash: string, enabled: boolean) {
  return queryOptions({
    queryKey: ['deletion', hash],
    queryFn: ({ signal }) =>
      apiGet<DeletionEstimate>(`/jobs/${encodeURIComponent(hash)}/deletion`, { signal }),
    enabled,
    // 估算是「現在磁碟上的樣子」。對話框重開一次就該重算，不拿上一次的答案賭它還成立。
    staleTime: 0,
  })
}

/** 照勾選的那幾格刪（`DELETE /jobs/{hash}`）。回的是**真的做掉了什麼**。 */
export async function deleteJob(hash: string, scope: DeleteScope) {
  const query = new URLSearchParams({
    unlink: String(scope.unlink),
    remove_torrent: String(scope.removeTorrent),
    delete_files: String(scope.deleteFiles),
    purge: String(scope.purge),
  })
  return apiDelete<JobDeleted>(`/jobs/${encodeURIComponent(hash)}?${query}`)
}
