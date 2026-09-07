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
