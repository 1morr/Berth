import type { ServiceKind, ServiceOrigin } from '../api/schemas'
import type { ConnectionReason } from '../api/setup'

/**
 * 三個服務怎麼被稱呼與描述。精靈、健康頁與服務設定頁共用——同一個服務在三頁上不該有
 * 三種寫法。
 */

export const SERVICE_LABEL = {
  jellyfin: 'service.jellyfin',
  qbittorrent: 'service.qbittorrent',
  prowlarr: 'service.prowlarr',
} as const satisfies Record<ServiceKind, string>

export const ORIGIN_LABEL = {
  bundled: 'origin.bundled',
  existing: 'origin.existing',
} as const satisfies Record<ServiceOrigin, string>

/**
 * `detail` 的意思由服務決定：版本號或索引站數量。Prowlarr 比下限舊的那一輪例外：還沒列站就停了，
 * `detail` 是它的版本（M4 票 17）。另一台 Jellyfin 回答時是它的伺服器名（M4 票 18）。
 */
export function detailLabel(
  kind: ServiceKind,
  reason?: ConnectionReason | null,
): 'detail.version' | 'detail.indexers' | 'detail.server' {
  if (reason === 'other_server') return 'detail.server'
  return kind === 'prowlarr' && reason !== 'version_unsupported'
    ? 'detail.indexers'
    : 'detail.version'
}

/**
 * qBittorrent 預設的 WebUI 封鎖：連錯 5 次、封 3600 秒（`web_ui_max_auth_fail_count` /
 * `web_ui_ban_duration`，4.4.5 與 5.0.4 的原始碼，brief §20.2）。只記在它的記憶體裡、重啟就清、登入成功
 * 歸零；被封時 Berth 讀不到那一台的偏好，所以說的是預設值。
 */
export const BAN_DEFAULTS = { limit: 5, minutes: 60 } as const

/** 連錯第幾次起在密碼欄下預警（M4 票 21）：再錯兩次就封。 */
export const BAN_WARNING_FROM = 3
