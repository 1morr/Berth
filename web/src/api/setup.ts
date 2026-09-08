import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type {
  Profile,
  QbittorrentSetup,
  RouteView,
  ServiceKind,
  ServiceOrigin,
  SetupStep,
} from './schemas'

/** `DetectionReason`：判定的理由，UI 逐服務顯示。 */
export type DetectionReason =
  | 'setup_pending'
  | 'setup_completed'
  | 'anonymous_ok'
  | 'auth_required'
  | 'no_indexers'
  | 'has_indexers'
  | 'api_key_missing'
  | 'not_deployed'
  | 'unreachable'
  | 'protocol_mismatch'
  | 'connected'

export interface ServiceDetection {
  kind: ServiceKind
  origin: ServiceOrigin
  reason: DetectionReason
  /** 探測到的實測值：版本號或索引站數量。空字串代表沒有。 */
  detail: string
  base_url: string
  /** 連線問題解掉了沒。沒解掉就要使用者補位址或憑證，第 2 步也還沒做完。 */
  resolved: boolean
}

export interface SetupStatus {
  completed: boolean
  current_step: number
  admin_created: boolean
  admin_username: string
  apply_to_services: boolean
  services: ServiceDetection[]
  waited_seconds: number
  window_seconds: number
}

export interface AdminInput {
  username: string
  password: string
  apply_to_services: boolean
}

export interface ConnectInput {
  base_url: string
  api_key?: string
  username?: string
  password?: string
}

export const setupStatusQueryOptions = queryOptions({
  queryKey: ['setup', 'status'],
  queryFn: () => apiGet<SetupStatus>('/setup/status'),
})

export function createAdmin(body: AdminInput): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/admin', body)
}

export function detectServices(restart = false): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/detect', { restart })
}

export function connectService(kind: ServiceKind, body: ConnectInput): Promise<SetupStatus> {
  return apiPost<SetupStatus>(`/setup/services/${kind}`, body)
}

/** `JellyfinStep`：plan §9.4 的九步，順序即宣告順序。 */
export const JELLYFIN_STEPS = [
  'public_info',
  'configuration',
  'admin_user',
  'libraries',
  'remote_access',
  'complete',
  'api_key',
  'plugin',
  'tasks',
] as const
export type JellyfinStep = (typeof JELLYFIN_STEPS)[number]

export interface JellyfinLibrary {
  name: string
  collection_type: string
  locations: string[]
  metadata_fetchers: string[]
  /** 掛了 TVDB 的 metadata fetcher：警告，不阻擋（brief §16.4）。 */
  uses_tvdb: boolean
  /** 「加入 Berth 路徑」會加的那一條。按之前就顯示它。 */
  berth_path: string
  has_berth_path: boolean
}

export interface JellyfinSetup {
  origin: ServiceOrigin
  base_url: string
  api_key_present: boolean
  steps: SetupStep[]
  libraries: JellyfinLibrary[]
  merge_versions_installed: boolean
  merge_movies_task_id: string
  merge_episodes_task_id: string
}

export const jellyfinSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'jellyfin'],
  queryFn: () => apiGet<JellyfinSetup>('/setup/jellyfin'),
})

export function bootstrapJellyfin(): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/bootstrap')
}

export function connectJellyfin(body: {
  username: string
  password: string
}): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/connect', body)
}

export function addLibraryPath(library: string): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/libraries/paths', { library })
}

export function installMergeVersions(): Promise<JellyfinSetup> {
  return apiPost<JellyfinSetup>('/setup/jellyfin/plugin')
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
export type IndexerKind = 'prowlarr' | 'torznab'

export interface IndexerOption {
  /** Prowlarr 的 `definitionName`，也是這一條纜繩的 key。 */
  definition_name: string
  name: string
  /** `public` / `semiPrivate` / `private`。 */
  privacy: string
  /** 這台 Prowlarr 上已經有這個站了。 */
  present: boolean
}

export interface IndexerSetup {
  origin: ServiceOrigin
  kind: IndexerKind
  base_url: string
  api_key_present: boolean
  reachable: boolean
  options: IndexerOption[]
  steps: SetupStep[]
  skipped: boolean
  sets_password: boolean
  error: string
}

export interface TmdbSetup {
  /** 用的是 Berth 內建的專案級憑證（使用者沒有覆寫）。 */
  using_project_credential: boolean
  steps: SetupStep[]
  skipped: boolean
}

export const indexerSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'indexers'],
  queryFn: () => apiGet<IndexerSetup>('/setup/indexers'),
})

export const tmdbSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'tmdb'],
  queryFn: () => apiGet<TmdbSetup>('/setup/tmdb'),
})

export function applyIndexers(indexers: string[]): Promise<IndexerSetup> {
  return apiPost<IndexerSetup>('/setup/indexers/apply', { indexers })
}

export function connectIndexer(body: {
  kind: IndexerKind
  base_url: string
  api_key: string
}): Promise<IndexerSetup> {
  return apiPost<IndexerSetup>('/setup/indexers/connect', body)
}

export function skipIndexers(skipped: boolean): Promise<IndexerSetup> {
  return apiPost<IndexerSetup>('/setup/indexers/skip', { skipped })
}

export function testTmdb(api_key: string): Promise<TmdbSetup> {
  return apiPost<TmdbSetup>('/setup/tmdb/test', { api_key })
}

export function skipTmdb(skipped: boolean): Promise<TmdbSetup> {
  return apiPost<TmdbSetup>('/setup/tmdb/skip', { skipped })
}

/** --- 第 7–8 步：媒體庫 → Route（plan §9.3 第 7–8 步、§9.5）--- */

export interface LibraryChoice {
  name: string
  collection_type: string
  locations: string[]
  berth_path: string
  has_berth_path: boolean
  uses_tvdb: boolean
  /** Berth 建得了 Route 的類型（movies / tvshows）。 */
  supported: boolean
  selected: boolean
  target_path: string
  profile: Profile
}

export interface RouteSetup {
  origin: ServiceOrigin
  library_root: string
  complete_root: string
  libraries: LibraryChoice[]
  routes: RouteView[]
  /** 至少一個 Route，而且每個都綠燈。完成鍵的前提。 */
  ready: boolean
  completed: boolean
}

export interface RouteSelectionInput {
  library: string
  target_path: string
  profile: Profile
}

export const routeSetupQueryOptions = queryOptions({
  queryKey: ['setup', 'routes'],
  queryFn: () => apiGet<RouteSetup>('/setup/routes'),
})

export function buildRoutes(selections: RouteSelectionInput[]): Promise<RouteSetup> {
  return apiPost<RouteSetup>('/setup/routes', { selections })
}

/** 寫下 `settings.setup.completed`。**之後 `setup/*` 就要登入了**（票 07）。 */
export function completeSetup(): Promise<SetupStatus> {
  return apiPost<SetupStatus>('/setup/complete')
}
