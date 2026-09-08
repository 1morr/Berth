import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type { HealthStatus, RouteView, ServiceKind, ServiceOrigin } from './schemas'

/** 匿名 `GET /api/health` 的總體判定。逐項的三態是 `schemas.HealthStatus`。 */
export type OverallStatus = 'ok' | 'degraded'

export interface Health {
  status: OverallStatus
  version: string
  /** 精靈跑完了沒。這一支是匿名的，所以還沒有人登入時也答得出來（票 07）。 */
  setup_completed: boolean
}

export interface ServiceHealth {
  kind: ServiceKind
  /** 套件內還是既有。修正建議分兩種，畫面照它挑（票 10）。 */
  origin: ServiceOrigin
  base_url: string
  status: HealthStatus
  /** 實測值：版本號、索引站數量。直接顯示，不翻譯。 */
  detail: string
  /** 失敗時服務回的原文（英文）。 */
  error: string
  checked_at: string | null
  /** 最後一次成功的時間（brief §16.2）。 */
  last_ok_at: string | null
  failures: number
  /** 有連線資訊可以檢查。索引站那一步可跳過，所以它可能是 false。 */
  configured: boolean
  /** 被改掉的建議偏好鍵（qBittorrent 專有，brief §16.3）。 */
  drift: string[]
}

/** `GET /api/health/detail`。設定頁的 `GET /api/settings/services` 回的是同一份。 */
export interface HealthDetail {
  status: OverallStatus
  checked_at: string | null
  /** 檢查間隔（秒）。畫面用它判斷「上次檢查」還算不算新鮮。 */
  interval_seconds: number
  services: ServiceHealth[]
  /** 第四項：所有 Route 的總結。 */
  routes_status: HealthStatus
  routes: RouteView[]
}

export const healthQueryOptions = queryOptions({
  queryKey: ['health'],
  queryFn: () => apiGet<Health>('/health'),
})

export const healthDetailQueryOptions = queryOptions({
  queryKey: ['health', 'detail'],
  queryFn: () => apiGet<HealthDetail>('/health/detail'),
})

/**
 * 立刻重跑四項檢查（plan §3.2 的「+ 手動」）。
 *
 * **開頁不會自動打這一支**：它會在 qBittorrent 建 category、在媒體庫寫探測檔再刪掉，
 * 那是一次維運動作，不該是「重整頁面」的副作用（shape brief §7）。
 */
export function runHealthCheck(): Promise<HealthDetail> {
  return apiPost<HealthDetail>('/health/check')
}
