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
 * `detail` 是它的版本（M4 票 17）。
 */
export function detailLabel(
  kind: ServiceKind,
  reason?: ConnectionReason | null,
): 'detail.version' | 'detail.indexers' {
  return kind === 'prowlarr' && reason !== 'version_unsupported'
    ? 'detail.indexers'
    : 'detail.version'
}
