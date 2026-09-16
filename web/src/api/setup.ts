import { queryOptions } from '@tanstack/react-query'

import { apiDelete, apiGet, apiPost } from './client'
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

export function detectServices(restart = false): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/detect', { restart } satisfies Schemas['DetectIn'])
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

/** --- 第 5–6 步：來源（plan §9.3 第 5–6 步、§8.3、§8.4）--- */

/** `IndexerKind`：既有路徑的兩種接法。 */
export type IndexerKind = Schemas['IndexerKind']

export type IndexerOption = Schemas['IndexerOptionOut']

export type IndexerSetup = Schemas['IndexerSetupOut']

/** 既有 Prowlarr 或任意 Torznab 的連線表單。 */
export type IndexerConnectInput = Schemas['IndexerConnectIn']

export type TmdbSetup = Schemas['TmdbSetupOut']

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

/** 第 6 步沒有 `skip`：憑證是使用者自備的必填項，測得過才走得到第 7 步（票 02b）。 */
export function testTmdb(api_key: string): Promise<TmdbSetup> {
  return apiPost<TmdbSetup>('/setup/tmdb/test', { api_key } satisfies Schemas['TmdbTestIn'])
}

/** --- 第 7–8 步：媒體庫 → Route（plan §9.3 第 7–8 步、§9.5）--- */

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
 * 第 7 步每條 Route 底下的刪除（票 14a）。與設定頁的 `deleteRoute` 同一個命令、同一種拒絕，
 * 只是跟著精靈的門禁：精靈跑完之前還沒有人登入得了，而 `/routes/*` 永遠只有 admin。
 */
export function deleteSetupRoute(id: number): Promise<void> {
  return apiDelete(`/setup/routes/${id}`)
}

/** 寫下 `settings.setup.completed`。**之後 `setup/*` 就要登入了**（票 07）。 */
export function completeSetup(): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/complete')
}
