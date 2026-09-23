import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost } from './client'
import { parseRefusal, type ReasonSet } from './refusal'
import type { Schemas } from './schemas'

/** 清單上的一件（`berth/api/issues.py` 的 `IssueOut`）。 */
export type Issue = Schemas['IssueOut']

/** 十一種型別的封閉集合（brief §9.1）。畫面逐種說一句話。 */
export type IssueType = Issue['type']

/**
 * 一列按得了哪幾顆（brief §9.1 的「預設建議動作」那一欄）。
 *
 * **後端算好放在 `issue.actions` 裡**，前端不重算一份規則：按得了什麼要看型別**與**這一筆
 * 的資料（指不到帳本的按不了重新鏈接），而那個判斷只能有一份。
 */
export type IssueAction = Schemas['IssueAction']

/** 一輪對帳（`ReconcileRunOut`）。`finished_at` 是 `null` 就是還在跑。 */
export type ReconcileRun = Schemas['ReconcileRunOut']

/** 上一輪與進行中的那一輪。 */
export type ReconcileStatus = Schemas['ReconcileStatusOut']

/** 一輪裡的一方（帳本 / 客戶端 / complete / 媒體庫 / Jellyfin）。 */
export type ReconcileSideReport = Schemas['SideOut']

/** 對帳比的各方（四方加上票 09 的 Jellyfin）。 */
export type ReconcileSide = ReconcileSideReport['side']

/** 動作被擋下來的理由（`berth/domain/enums.py` 的 `IssueRefusal`）。 */
export type IssueRefusal = Schemas['IssueRefusal']

/**
 * 執行期認得的那幾種。**少一種或多一種都是編譯錯誤**（同 `api/jobs.ts`）：
 * 後端加一種拒絕理由時，紅的是這裡，而不是畫面上少一句話。
 */
const REASONS: ReasonSet<IssueRefusal> = {
  issue_missing: true,
  issue_not_open: true,
  action_not_available: true,
  source_missing: true,
  relink_failed: true,
  client_unreachable: true,
  reconcile_running: true,
  in_use: true,
  size_differs: true,
  jellyfin_unreachable: true,
  delete_failed: true,
  source_unavailable: true,
  resubmit_failed: true,
  route_unusable: true,
  media_required: true,
  unclaimable: true,
}

/** 這一次失敗是「後端說不行」還是「網路壞了」。認不得的理由回 `null`。 */
export function parseIssueRefusal(error: unknown) {
  return parseRefusal(error, REASONS)
}

/** 還沒有人決定的那幾件，最近偵測到的在前面。**只有 `open`**——這是工作清單不是歷史。 */
export function issuesQueryOptions() {
  return queryOptions({ queryKey: ['issues'], queryFn: () => apiGet<Issue[]>('/issues') })
}

/**
 * 上一輪與進行中的那一輪。
 *
 * `refetchInterval` 只在**跑的時候**開著：對帳一天一輪，平常輪詢它是在問一個不會變的答案。
 */
export function reconcileQueryOptions() {
  return queryOptions({
    queryKey: ['reconcile'],
    queryFn: () => apiGet<ReconcileStatus>('/reconcile'),
    refetchInterval: (query) => (query.state.data?.current ? 1000 : false),
  })
}

/** 開一輪對帳。回的是這一輪的樣子（202，它在背景跑）。 */
export async function startReconcile() {
  return apiPost<ReconcileRun>('/reconcile')
}

/**
 * 按下那一顆。做得到才會回一個 `resolved` 的它。
 *
 * `media` 只有認領類的兩顆要（重新入庫、認領 torrent，M2 票 10）：管理員選的那一部作品。
 */
export async function resolveIssue(id: number, action: IssueAction, media = '') {
  return apiPost<Issue>(`/issues/${id}/resolve`, {
    action,
    media,
  } satisfies Schemas['IssueResolveIn'])
}

/** 「我知道了，不用管它」。那個檔案仍然不在，所以下一輪對帳會再開一筆新的。 */
export async function ignoreIssue(id: number) {
  return apiPost<Issue>(`/issues/${id}/ignore`)
}
