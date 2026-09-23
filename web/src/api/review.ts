import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import { parseRefusal, type ReasonSet } from './refusal'
import type { Schemas } from './schemas'

/** 整份佇列（`berth/api/review.py` 的 `ReviewQueueOut`）。`rows` 最多 200 列，`total` 是全部幾件。 */
export type ReviewQueue = Schemas['ReviewQueueOut']

/**
 * 佇列上的一列。**以 `kind` 區分形狀**：比對 `row.kind === 'audit'` 之後 TS 就知道它有哪幾格。
 * 五種的其餘兩種（`unmatched`、`duplicate`）由票 08 加進這個聯集。
 */
export type ReviewRow = ReviewQueue['rows'][number]

export type PlanReviewRow = Schemas['PlanRowOut']

export type AuditReviewRow = Schemas['AuditRowOut']

export type IssueReviewRow = Schemas['IssueRowOut']

/**
 * 佇列上**現在會出現**的幾種（`domain.ReviewKind` 的子集）。取自列的聯集而不是那個 enum：
 * 畫面的分段表以它為鍵，票 07 把 `plan` 加進聯集時，少寫那一格是 `tsc` 的事。
 */
export type ReviewKind = ReviewRow['kind']

/** plan 那一列的兩顆：核准、拒絕（打的是 `api/plans.ts`）。 */
export type PlanDecision = Schemas['PlanDecision']

/** audit 那一列的兩顆。 */
export type AuditAction = Schemas['AuditAction']

/** 確認或撤銷被擋下來的理由（`domain.ReviewRefusal`）。 */
export type ReviewRefusal = Schemas['ReviewRefusal']

/** 執行期認得的那幾種。**少一種或多一種都是編譯錯誤**（同 `api/issues.ts`）。 */
const REASONS: ReasonSet<ReviewRefusal> = {
  ledger_missing: true,
  not_audited: true,
  unlink_failed: true,
}

/** 這一次失敗是「後端說不行」還是「網路壞了」。認不得的理由回 `null`。 */
export function parseReviewRefusal(error: unknown) {
  return parseRefusal(error, REASONS)
}

/** 需要人動手的排前面，同一類之內舊的在前（plan §6）。**前端不重排**：排序只有後端一份。 */
export function reviewQueryOptions() {
  return queryOptions({ queryKey: ['review'], queryFn: () => apiGet<ReviewQueue>('/review') })
}

/** 「它是對的」：清掉兩處 audit 旗標，檔案不動。 */
export async function confirmAudit(ledgerId: number) {
  return apiPost<void>(`/review/audit/${ledgerId}/confirm`)
}

/** 「它是錯的」：拆掉那個硬鏈接、刪掉帳本那一列，那一筆下載回到待審核。 */
export async function undoAudit(ledgerId: number) {
  return apiPost<void>(`/review/audit/${ledgerId}/undo`)
}
