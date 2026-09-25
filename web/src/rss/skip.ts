import type { TFunction } from 'i18next'

import type { SkipReason } from '../api/rss'

/**
 * 一筆 Feed Item 為什麼沒下載（`domain.SkipReason`，M3 票 10）：code 挑句子（`rss.skip.*`），參數是原文。
 * 排除與去重擋下的都不是錯誤，所以這一句說的是「為什麼」，不是「出了什麼事」。
 */
export function skipText(t: TFunction, reason: SkipReason): string {
  // `as never`：鍵是逐 code 的聯集（同 `grounds.ts`）。參數的形狀由後端的 `SKIP_PARAMS` 定、
  // `test_skip_reasons.py` 逐句比對。
  return t(`rss.skip.${reason.code}`, reason.params as never)
}
