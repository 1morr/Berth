import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import type { Job } from './jobs'
import type { Schemas } from './schemas'

/** 一份 Import Plan（`berth/api/plans.py` 的 `PlanOut`、CONTEXT.md）。 */
export type Plan = Schemas['PlanOut']

/** Plan 裡一個檔案的決定。 */
export type PlanItem = Schemas['PlanItemOut']

/** `preplan` / `auto` / `pending_review` / `approved` / `rejected` / `applied` / `failed`。 */
export type PlanStatus = Plan['status']

/** `import` / `extra` / `subtitle` / `skip` / `unmatched` / `review`。 */
export type PlanAction = PlanItem['action']

/** brief §6.5 的三級。 */
export type Confidence = PlanItem['confidence']

/** 為什麼停下來等人（`domain.ReviewReason`）。`auto` 的 Plan 是 `null`。 */
export type ReviewReason = NonNullable<Plan['summary']['review_reason']>

/**
 * 一筆 Job 現在那一份計劃。
 *
 * **key 掛在那筆 Job 底下**（`['jobs', hash, …]`）：SSE 讓 `['jobs']` 整個前綴失效
 * （`api/events.ts`），所以背景迴圈把 Plan 算出來的那一刻，展開中的那一列自己就會重問。
 *
 * 列展開時才問，與時間線同一條規則：一份清單裡多數列不會被展開。
 */
export function planQueryOptions(hash: string, planId: number | null, enabled: boolean) {
  return queryOptions({
    queryKey: ['jobs', hash, 'plan', planId],
    queryFn: () => apiGet<Plan>(`/plans/${planId}`),
    enabled: enabled && planId !== null,
  })
}

/**
 * 重新算一份 Plan（plan §6 jobs 群組）。
 *
 * 回的是**那一筆 Job**而不是 Plan：按下去之後畫面上要重畫的是那一列（狀態可能從
 * 「待審核」變成「入庫中」），而逐檔的決定由 `planQueryOptions` 跟著新的 `plan_id` 去要。
 */
export async function replanJob(hash: string) {
  return apiPost<Job>(`/jobs/${encodeURIComponent(hash)}/replan`)
}
