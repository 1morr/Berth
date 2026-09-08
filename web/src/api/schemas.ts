/**
 * 跨頁面共用的 API 形狀，對應後端的 `berth/api/schemas.py`。
 *
 * 一條纜繩、一個 Route、一個 qBittorrent 偏好差異這三種東西同時出現在精靈、健康頁與設定頁。
 * 形狀寫兩份的話，改了一邊另一邊會悄悄少一個欄位，而型別只會擋住其中一個。
 */

/** 與 `berth/domain/enums.py` 的 `ServiceKind` 對齊。 */
export const SERVICE_KINDS = ['jellyfin', 'qbittorrent', 'prowlarr'] as const
export type ServiceKind = (typeof SERVICE_KINDS)[number]

/** `ServiceOrigin`：逐服務的判定。 */
export type ServiceOrigin = 'bundled' | 'existing' | 'pending' | 'timeout'

/** `StepStatus`：一條纜繩的結果。 */
export type StepStatus = 'ok' | 'skipped' | 'failed' | 'running' | 'pending'

export interface SetupStep {
  /** 精靈的步驟名或 `RouteCheck`。後端可能加新的，所以型別放寬成 string。 */
  step: string
  status: StepStatus
  /** 實測值：版本號、路徑、inode。直接顯示，不翻譯。 */
  detail: string
  /** 失敗時服務回的原文（英文）。 */
  error: string
}

/** `RouteCheck`：一個 Route 的五條纜繩，順序即檢查順序。 */
export const ROUTE_CHECKS = [
  'category',
  'download_path',
  'library_path',
  'probe_visible',
  'hardlink',
] as const
export type RouteCheck = (typeof ROUTE_CHECKS)[number]

/** `Profile`：Route 的命名與解析偏好（CONTEXT.md）。 */
export const PROFILES = ['standard', 'anime'] as const
export type Profile = (typeof PROFILES)[number]

/** 一個 Route 或一個服務上一次檢查的結果（後端 `domain.HealthStatus`）。 */
export type HealthStatus = 'unknown' | 'ok' | 'failed'

export interface RouteView {
  slug: string
  name: string
  /** Jellyfin 媒體庫的名字。 */
  library: string
  collection_type: 'movies' | 'tvshows'
  target_path: string
  category: string
  /** 這個 category 的 save path，也就是硬鏈接的來源目錄。 */
  save_path: string
  profile: Profile
  enabled: boolean
  health: HealthStatus
  checks: SetupStep[]
  /** 硬鏈接回 `EXDEV`：兩個目錄在 Berth 內是不同掛載（brief §4.4）。 */
  cross_device: boolean
  checked_at: string | null
  /** 最後一次五條纜繩全綠的時間（brief §16.2）。 */
  last_ok_at: string | null
}

export interface PreferenceDiff {
  /** `app/setPreferences` 的鍵名。畫面顯示的與送出去的是同一個字串。 */
  key: string
  current: string
  recommended: string
  differs: boolean
}

/** 精靈第 4 步與設定頁的漂移還原共用（brief §16.3）。 */
export interface QbittorrentSetup {
  origin: ServiceOrigin
  base_url: string
  version: string
  webapi_version: string
  supported: boolean
  /** 這一步做不下去：版本太舊或連不上。 */
  blocked: boolean
  reachable: boolean
  diffs: PreferenceDiff[]
  steps: SetupStep[]
  temp_path_warning: boolean
  sets_password: boolean
  error: string
}
