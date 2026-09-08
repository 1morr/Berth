import type { ServiceKind, ServiceOrigin } from '../api/schemas'

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
  pending: 'origin.pending',
  timeout: 'origin.timeout',
} as const satisfies Record<ServiceOrigin, string>

/** `detail` 的意思由服務決定：版本號或索引站數量。 */
export function detailLabel(kind: ServiceKind): 'detail.version' | 'detail.indexers' {
  return kind === 'prowlarr' ? 'detail.indexers' : 'detail.version'
}
