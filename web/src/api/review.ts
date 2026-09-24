import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import { parseRefusal, type ReasonSet } from './refusal'
import type { Schemas } from './schemas'

/** 整份佇列（`berth/api/review.py` 的 `ReviewQueueOut`）。`rows` 最多 200 列，`total` 是全部幾件。 */
export type ReviewQueue = Schemas['ReviewQueueOut']

/** 佇列上的一列。**以 `kind` 區分形狀**：比對 `row.kind === 'audit'` 之後 TS 就知道它有哪幾格。 */
export type ReviewRow = ReviewQueue['rows'][number]

export type PlanReviewRow = Schemas['PlanRowOut']

export type AuditReviewRow = Schemas['AuditRowOut']

/** 對不到、留在 complete 原位的檔案。三個動作打 `api/files.ts` 的 `rematch`（帶 `job_file_id`）。 */
export type UnmatchedReviewRow = Schemas['UnmatchedRowOut']

/** 規劃時與媒體庫裡已有的一份重複而被略過的檔案（brief §7.8）。 */
export type DuplicateReviewRow = Schemas['DuplicateRowOut']

/** duplicate 那一列的三顆：取代舊版、保留兩者、跳過。 */
export type DuplicateDecision = Schemas['DuplicateDecision']

/** 決定完之後：新的一份落在哪裡（跳過時是空字串）。 */
export type DuplicateDecided = Schemas['DuplicateDecidedOut']
/** 撤銷之後媒體庫裡那個檔案怎麼了：拆掉了，或那裡的已經不是 Berth 放的那一個（M3 票 01）。 */
export type AuditUndone = Schemas['AuditUndoneOut']

/** 「全部確認」之後：確認了幾列、跳過了幾列（已經被別處確認或撤銷的）。 */
export type AuditsConfirmed = Schemas['AuditsConfirmedOut']

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

/** 媒體庫頁「待審 / 對不到」的那兩類（M2 票 14）。 */
export type LibraryReviewKind = Extract<ReviewKind, 'plan' | 'unmatched'>

/**
 * 一個 Jellyfin 媒體庫的「待審 / 對不到」（M2 票 14）：`plan` 與 `unmatched` 兩類、Route 指向它的。`total` 只算
 * 這兩類，`queue_total` 是整份佇列。快取鍵在 `['review']` 底下：任何一列按完之後重問整份佇列時，這一份一起重問。
 */
export function libraryReviewQueryOptions(libraryId: string) {
  return queryOptions({
    queryKey: ['review', 'library', libraryId],
    queryFn: () => apiGet<ReviewQueue>(`/review?library=${encodeURIComponent(libraryId)}`),
  })
}

/** 「它是對的」：清掉兩處 audit 旗標，檔案不動。 */
export async function confirmAudit(ledgerId: number) {
  return apiPost<void>(`/review/audit/${ledgerId}/confirm`)
}

/**
 * 「全部確認」（M3 票 05）：同一個 Job 一組，或 audit 段整段。送的是**畫面上列出的**那幾個帳本 id，
 * 按下之後才進來的 audit 不會被順手確認掉。已經被別處決定過的列後端跳過，不是失敗。
 */
export async function confirmAudits(ledgerIds: readonly number[]) {
  return apiPost<AuditsConfirmed>('/review/audit/confirm', { ledger_ids: ledgerIds })
}

/** 「它是錯的」：拆掉那個硬鏈接、刪掉帳本那一列，那一筆下載回到待審核。 */
export async function undoAudit(ledgerId: number) {
  return apiPost<AuditUndone>(`/review/audit/${ledgerId}/undo`)
}

/** 重複版本的一顆。拒絕的形狀與 rematch 相同（`api/files.ts` 的 `rematchRefusalText`）。 */
export async function decideDuplicate(itemId: number, decision: DuplicateDecision) {
  return apiPost<DuplicateDecided>(`/review/duplicate/${itemId}/${decision}`)
}
