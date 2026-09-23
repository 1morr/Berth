import type { TFunction } from 'i18next'

import { apiPost } from './client'
import { parseRefusal, type ReasonSet } from './refusal'
import type { Schemas } from './schemas'

/**
 * 修正一個檔案（`berth/api/files.py`、brief §9.4、M2 票 08）。已入庫的帶 `ledger_id`，對不到的帶
 * `job_file_id`，**恰好一個**。`/review` 的對不到那一列與 Media 詳情打的是這同一支。
 */
export type RematchBody = Schemas['RematchIn']

/** 改完之後：記下這一次修正的單列 Plan，與它現在在媒體庫的哪裡（忽略時是空字串）。 */
export type RematchResult = Schemas['RematchOut']

/** 擋下來的理由（`domain.RematchRefusal`）。重複版本的三顆也回這一種。 */
export type RematchRefusal = Schemas['RematchRefusal']

/** 執行期認得的那幾種。**少一種或多一種都是編譯錯誤**（同 `api/review.ts`）。 */
const REASONS: ReasonSet<RematchRefusal> = {
  ledger_missing: true,
  file_missing: true,
  not_unmatched: true,
  plan_pending: true,
  not_duplicate: true,
  action_not_allowed: true,
  episode_required: true,
  episode_range_reversed: true,
  episode_not_allowed: true,
  media_missing: true,
  route_missing: true,
  target_taken: true,
  link_failed: true,
  unlink_failed: true,
}

/** 這一次失敗是「後端說不行」還是「網路壞了」。認不得的理由回 `null`。 */
export function parseRematchRefusal(error: unknown) {
  return parseRefusal(error, REASONS)
}

/** 擋下來時那一句：理由翻譯，`detail`（檔名、路徑或系統原文）原文接在後面。 */
export function rematchRefusalText(t: TFunction, error: unknown): string {
  const said = parseRematchRefusal(error)
  if (!said) return t('rematch.failed')
  return [t(`rematch.refusal.${said.reason}`), said.detail].filter(Boolean).join(' ')
}

/** 建新鏈接 → 拆舊鏈接 → 改帳本 → 通知掃描，一律經過 Plan。 */
export async function rematch(body: RematchBody) {
  return apiPost<RematchResult>('/files/rematch', body)
}
