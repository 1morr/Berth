import { queryOptions } from '@tanstack/react-query'

import { ApiError, apiDelete, apiGet, apiPost, apiPut } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { QbittorrentSetup, Schemas, ServiceKind } from './schemas'

/** `DetectionReason`：判定的理由，UI 逐服務顯示。 */
export type DetectionReason = Schemas['DetectionReason']

export type ServiceDetection = Schemas['ServiceDetectionOut']

export type SetupStatus = Schemas['SetupStatusOut']

export type AdminInput = Schemas['AdminIn']

/** 既有服務的連線表單。每個服務只用得到其中幾個欄位。 */
export type ConnectInput = Schemas['ConnectIn']

export const setupStatusQueryOptions = queryOptions({
  queryKey: ['setup', 'status'],
  queryFn: () => apiGet<SetupStatus>('/setup/status'),
})

export function createAdmin(body: AdminInput): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/admin', body)
}

/**
 * 第 2 步的探測。給了 `kind` 就只重探那一個服務（票 06d 的「重新偵測這個服務」）；
 * 沒給就是整輪。
 */
export function detectServices(restart = false, kind?: ServiceKind): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/detect', { restart, kind } satisfies Schemas['DetectIn'])
}

export function connectService(kind: ServiceKind, body: ConnectInput): Promise<SetupStatus> {
  return apiPost<SetupStatus>(`/setup/services/${kind}`, body)
}

/**
 * `JellyfinStep`：plan §9.4 的七步，順序即宣告順序。
 *
 * 後端把 `StepOut.step` 宣告成 `str`，所以這個集合在 OpenAPI 裡不存在——它是 UI 的
 * 顯示順序，不是 API 的形狀（`QBITTORRENT_STEPS` 同理）。
 */
export const JELLYFIN_STEPS = [
  'public_info',
  'configuration',
  'admin_user',
  'libraries',
  'remote_access',
  'complete',
  'api_key',
] as const
export type JellyfinStep = (typeof JELLYFIN_STEPS)[number]

export type JellyfinLibrary = Schemas['LibraryOut']

export type JellyfinSetup = Schemas['JellyfinSetupOut']

/** 既有 Jellyfin：以管理員帳密換 API key。 */
export type JellyfinConnectInput = Schemas['JellyfinConnectIn']

export const jellyfinSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'jellyfin'],
  queryFn: () => apiGet<JellyfinSetup>('/setup/jellyfin'),
})

export function bootstrapJellyfin(): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/bootstrap')
}

/** 套件內要建的一個媒體庫，以及它是不是已經在 Jellyfin 建好了（票 06f）。 */
export type BundledLibrary = Schemas['BundledLibraryOut']

/** 送去存的一列：內容類型 + 名稱 + 資料夾。 */
export type LibraryDraft = Schemas['BundledLibraryIn']

/**
 * 存下套件內要建的媒體庫（票 06f）。剖面改一次存一次（關掉瀏覽器回來還在），按「開始靠泊」
 * 之前也先存一次——`bootstrap` 讀的是存下來的那一份。
 */
export function saveBundledLibraries(libraries: LibraryDraft[]): Promise<JellyfinSetup> {
  return apiPut<JellyfinSetup>('/setup/jellyfin/bundled', {
    libraries,
  } satisfies Schemas['BundledLibrariesIn'])
}

export type BundledLibraryRefusal = Schemas['BundledLibraryRefusal']

/** 清單的拒絕，另帶是第幾列（0 起算）；空清單與「建好的那一列不見了」說不出是哪一列。 */
export interface BundledRefusal extends Refusal<BundledLibraryRefusal> {
  row?: number
}

/** 執行期認得的那幾種。少一種或多一種都是編譯錯誤。 */
const BUNDLED_REASONS: ReasonSet<BundledLibraryRefusal> = {
  empty: true,
  name_missing: true,
  name_taken: true,
  folder_missing: true,
  folder_taken: true,
  folder_outside_root: true,
  folder_characters: true,
  built_changed: true,
}

/** 清單被後端擋下來的理由。剖面先用同一組規則擋過，所以到得了這裡的多半是另一個分頁改過了。 */
export function bundledRefusalOf(error: unknown): BundledRefusal | null {
  const refusal = parseRefusal(error, BUNDLED_REASONS)
  // 第二個條件在 `parseRefusal` 回了東西之後永遠成立，寫出來是為了 TypeScript 的縮窄
  // （`routeRefusalOf` 同一個寫法）。
  if (refusal === null || !(error instanceof ApiError)) return refusal
  const { row } = error.detail as Partial<Schemas['BundledLibraryRefusalOut']>
  return typeof row === 'number' ? { ...refusal, row } : refusal
}

export function connectJellyfin(body: JellyfinConnectInput): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/connect', body)
}

export function addLibraryPath(library: string): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/libraries/paths', {
    library,
  } satisfies Schemas['LibraryPathIn'])
}

/** --- 第 4 步：qBittorrent（plan §9.3 第 4 步、§8.1）--- */

/** `QbittorrentStep`：一個鍵一條纜繩，值就是 `app/setPreferences` 的鍵名。 */
export const QBITTORRENT_STEPS = [
  'temp_path_enabled',
  'temp_path',
  'save_path',
  'auto_tmm_enabled',
  'category_changed_tmm_enabled',
  'web_ui_password',
] as const
export type QbittorrentStep = (typeof QBITTORRENT_STEPS)[number]

export const qbittorrentSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'qbittorrent'],
  queryFn: () => apiGet<QbittorrentSetup>('/setup/qbittorrent/diff'),
})

export function applyQbittorrent(): Promise<QbittorrentSetup> {
  return apiPost<QbittorrentSetup>('/setup/qbittorrent/apply')
}

/** --- 第 6、7 步：索引站與 TMDB（plan §9.3 第 6–7 步、§8.3、§8.4；票 06e 拆成兩個泊位）--- */

/** `IndexerKind`：既有路徑的兩種接法。 */
export type IndexerKind = Schemas['IndexerKind']

export type IndexerOption = Schemas['IndexerOptionOut']

export type IndexerSetup = Schemas['IndexerSetupOut']

/** 既有 Prowlarr 或任意 Torznab 的連線表單。 */
export type IndexerConnectInput = Schemas['IndexerConnectIn']

export type TmdbSetup = Schemas['TmdbSetupOut']

/** 試搜的整份結果：逐站一列（票 06e）。 */
export type TrialSearchResult = Schemas['IndexerSearchOut']

export type SiteSearch = Schemas['SiteSearchOut']

export const indexerSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'indexers'],
  queryFn: () => apiGet<IndexerSetup>('/setup/indexers'),
})

export const tmdbSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'tmdb'],
  queryFn: () => apiGet<TmdbSetup>('/setup/tmdb'),
})

export function applyIndexers(indexers: string[]): Promise<IndexerSetup> {
  return apiPost<IndexerSetup>('/setup/indexers/apply', {
    indexers,
  } satisfies Schemas['IndexerApplyIn'])
}

export function connectIndexer(body: IndexerConnectInput): Promise<IndexerSetup> {
  return apiPost<IndexerSetup>('/setup/indexers/connect', body)
}

export function skipIndexers(skipped: boolean): Promise<IndexerSetup> {
  return apiPost<IndexerSetup>('/setup/indexers/skip', { skipped } satisfies Schemas['SkipIn'])
}

/**
 * 加入之後的試搜（票 06e）。只讀，但要 Prowlarr 現場去連每一個站，所以是按了才問，
 * 不是開頁就問。空白的查詢回各站最新的發佈。
 */
export function searchIndexers(query: string): Promise<TrialSearchResult> {
  return apiGet<TrialSearchResult>(`/setup/indexers/search?${new URLSearchParams({ query })}`)
}

/** 從套件內的 Prowlarr 移除一站（票 06e）。回的是整份索引站狀態：那一站與它的加入結果都不在了。 */
export function removeIndexer(id: number): Promise<IndexerSetup> {
  return apiDelete<IndexerSetup>(`/setup/indexers/${id}`)
}

/** 第 7 步沒有 `skip`：憑證是使用者自備的必填項，測得過才走得到完成（票 02b）。 */
export function testTmdb(api_key: string): Promise<TmdbSetup> {
  return apiPost<TmdbSetup>('/setup/tmdb/test', { api_key } satisfies Schemas['TmdbTestIn'])
}

/** --- 第 5 步：媒體庫 → Route（plan §9.3 第 5 步、§9.5）--- */

export type LibraryChoice = Schemas['LibraryChoiceOut']

export type RouteSetup = Schemas['RouteSetupOut']

export type RouteSelectionInput = Schemas['RouteSelectionIn']

export const routeSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'routes'],
  queryFn: () => apiGet<RouteSetup>('/setup/routes'),
})

export function buildRoutes(selections: RouteSelectionInput[]): Promise<RouteSetup> {
  return apiPost<RouteSetup>('/setup/routes', { selections } satisfies Schemas['RoutesIn'])
}

/**
 * 第 5 步每條 Route 底下的刪除（票 14a）。與設定頁的 `deleteRoute` 同一個命令、同一種拒絕，
 * 只是跟著精靈的門禁：精靈跑完之前還沒有人登入得了，而 `/routes/*` 永遠只有 admin。
 */
export function deleteSetupRoute(id: number): Promise<void> {
  return apiDelete(`/setup/routes/${id}`)
}

/** 寫下 `settings.setup.completed`。**之後 `setup/*` 就要登入了**（票 07）。 */
export function completeSetup(): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/complete')
}
