import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, apiPut } from './client'
import type { Job } from './jobs'
import { parseRefusal, type ReasonSet } from './refusal'
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

/** 逐檔的一條理由：code 加參數，句子在前端（`plans/reasonText.ts`，M2 票 07）。 */
export type ItemReason = PlanItem['reasons'][number]

/** 檔案分類（`domain.FileKind`，brief §6.2）。 */
export type FileKind = PlanItem['kind']

/** 一列要改成什麼（`ItemEditIn`）。季集只屬於劇集的入庫，其餘處置三格都是 `null`。 */
export type ItemEdit = Schemas['ItemEditIn']

/** 改、核准、拒絕被擋下來的理由（`domain.PlanRefusal`）。 */
export type PlanRefusal = Schemas['PlanRefusal']

/** 執行期認得的那幾種。**少一種或多一種都是編譯錯誤**（同 `api/review.ts`）。 */
const REASONS: ReasonSet<PlanRefusal> = {
  plan_missing: true,
  not_pending: true,
  item_missing: true,
  item_applied: true,
  action_not_allowed: true,
  episode_required: true,
  episode_range_reversed: true,
  episode_not_allowed: true,
  media_missing: true,
  target_clash: true,
  undecided: true,
}

/** 這一次失敗是「後端說不行」還是「網路壞了」。認不得的理由回 `null`。 */
export function parsePlanRefusal(error: unknown) {
  return parseRefusal(error, REASONS)
}

/**
 * 一筆 Job 現在那一份計劃。
 *
 * **key 掛在那筆 Job 底下**（`['jobs', hash, …]`）：SSE 讓 `['jobs']` 整個前綴失效
 * （`api/events.ts`），所以背景迴圈把 Plan 算出來的那一刻，詳情頁與審核佇列上的那一份自己就會重問。
 * 還沒算過（`planId` 是 `null`）就不問——那就是答案。
 */
export function planQueryOptions(hash: string, planId: number | null) {
  return queryOptions({
    queryKey: ['jobs', hash, 'plan', planId],
    queryFn: () => apiGet<Plan>(`/plans/${planId}`),
    enabled: planId !== null,
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

/**
 * 逐列改（M2 票 07）。回的是**改完的整份**：改過那一列的新目標路徑、跟著搬的字幕都在裡面，
 * 前端不重算任何一條路徑（命名是後端的純函式，plan §5）。
 */
export async function editPlanItems(planId: number, items: ItemEdit[]) {
  return apiPut<Plan>(`/plans/${planId}/items`, { items })
}

/** 核准＝照提案入庫：`review → importing`。改過幾列都是這一支（批次核准不是另一條路）。 */
export async function approvePlan(planId: number) {
  return apiPost<Plan>(`/plans/${planId}/approve`)
}

/** 拒絕：`review → completed`，Berth 整份重新規劃。檔案不動。 */
export async function rejectPlan(planId: number) {
  return apiPost<void>(`/plans/${planId}/reject`)
}
