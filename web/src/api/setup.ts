import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'

/** 與 `berth/domain/enums.py` 的 `ServiceKind` 對齊。 */
export const SERVICE_KINDS = ['jellyfin', 'qbittorrent', 'prowlarr'] as const
export type ServiceKind = (typeof SERVICE_KINDS)[number]

/** `ServiceOrigin`：逐服務的判定。 */
export type ServiceOrigin = 'bundled' | 'existing' | 'pending' | 'timeout'

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

/** `StepStatus`：精靈裡一個步驟的結果。 */
export type StepStatus = 'ok' | 'skipped' | 'failed' | 'running' | 'pending'

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

export interface SetupStep {
  /** `JellyfinStep` 之一。後端可能加新的步驟，所以型別放寬成 string。 */
  step: string
  status: StepStatus
  /** 實測值：版本號、建了哪幾個媒體庫、任務 id。直接顯示，不翻譯。 */
  detail: string
  /** 失敗時 Jellyfin 回的原文（英文）。 */
  error: string
}

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
