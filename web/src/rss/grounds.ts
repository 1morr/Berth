import type { TFunction } from 'i18next'

import type { BindReason, BindReasonCode } from '../api/rss'
import type { ReasonSet } from '../api/refusal'

/**
 * 自動綁定的理由（`domain.BindReason`，M3 票 09）：code 挑句子（`rss.grounds.*`），參數是原文。
 *
 * 三處說同一套話：待綁定那一列（為什麼沒綁）、綁好的那一列（`bound_by = system` 的依據），與
 * 那個 Series 送出的 Job 的時間線（`created` 事件的 `grounds`）。
 */

/** 認得的 code。**少一種、多一種都是編譯錯誤**（`api/refusal.ts` 的 `ReasonSet`）。 */
const CODES: ReasonSet<BindReasonCode> = {
  title_equal: true,
  premiere_near: true,
  release_near: true,
  only_route: true,
  no_candidate: true,
  premiere_far: true,
  several_candidates: true,
  no_premiere: true,
  lookup_failed: true,
  route_ambiguous: true,
  no_route: true,
}

export function groundText(t: TFunction, reason: BindReason): string {
  // `as never`：鍵是逐 code 的聯集，i18next 的型別因此要求每一句的參數同時都在（`plans/reasonText.ts`
  // 同一個理由）。參數的形狀由後端的 `BIND_PARAMS` 定、`test_bind_reasons.py` 逐句比對。
  return t(`rss.grounds.${reason.code}`, reason.params as never)
}

/**
 * 事件 payload 裡的 `grounds`（沒有型別，是後端寫進 JSON 的那一份）→ 認得的那幾條。
 * 認不得的 code 略過：後端跑在前面時少一句話，不印一條沒翻譯的 key。
 */
export function parseGrounds(raw: unknown): BindReason[] {
  if (!Array.isArray(raw)) return []
  return raw.flatMap((entry: unknown) => {
    if (typeof entry !== 'object' || entry === null) return []
    const { code, params } = entry as { code?: unknown; params?: unknown }
    if (typeof code !== 'string' || !Object.hasOwn(CODES, code)) return []
    const safe = typeof params === 'object' && params !== null ? params : {}
    return [{ code: code as BindReasonCode, params: safe as BindReason['params'] }]
  })
}
