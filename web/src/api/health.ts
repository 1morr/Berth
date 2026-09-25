import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type { Schemas } from './schemas'

/** 匿名 `GET /api/health`：總體判定、版本、精靈跑完了沒。 */
export type Health = Schemas['Health']

export type ServiceHealth = Schemas['ServiceHealthOut']

/** `GET /api/health/detail`。設定頁的 `GET /api/settings/services` 回的是同一份。 */
export type HealthDetail = Schemas['HealthDetailOut']

export const healthQueryOptions = queryOptions({
  queryKey: ['health'],
  queryFn: () => apiGet<Health>('/health'),
})

export const healthDetailQueryOptions = queryOptions({
  queryKey: ['health', 'detail'],
  queryFn: () => apiGet<HealthDetail>('/health/detail'),
})

/** `GET /api/health/budget`：一個站一份請求預算的現況（M3 票 20）。 */
export type RequestBudget = Schemas['BudgetOut']
export type SiteBudget = Schemas['SiteBudgetOut']

export const budgetQueryOptions = queryOptions({
  queryKey: ['health', 'budget'],
  queryFn: () => apiGet<RequestBudget>('/health/budget'),
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
