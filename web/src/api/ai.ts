import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPost, apiPut } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { Schemas } from './schemas'

/**
 * 設定 → AI（M5）：API 格式、base URL、API key、模型，與一次三請求的測試。
 * API key 原文只往後端去、永遠不回來：回來的只有「有沒有存」（`api_key_present`）。
 */

export type AiSettings = Schemas['AiSettingsOut']

export type AiSettingsBody = Schemas['AiSettingsIn']

export type AiToolTest = Schemas['AiToolTestOut']

export type AiTest = Schemas['AiTestOut']

export type AiModels = Schemas['AiModelsOut']

/** 一次請求為什麼沒成（`AiFailure`）。畫面照它挑人話與補法，原文收進技術細節。 */
export type AiFailure = Schemas['AiFailure']

/** 模型不支援工具呼叫時的樣子（`ToolGap`）。 */
export type ToolGap = Schemas['ToolGap']

export type AiProbeStep = Schemas['AiProbeStep']

export type AiRefusal = Schemas['AiRefusal']

/** 執行期認得的那幾種。少一種或多一種都是編譯錯誤（同 `api/notify.ts`）。 */
const REASONS: ReasonSet<AiRefusal> = {
  base_url_invalid: true,
  not_ready: true,
}

/** 認不得的理由是 `null`，畫面照請求為什麼沒成說（`RequestFailed`）。 */
export function aiRefusalOf(error: unknown): Refusal<AiRefusal> | null {
  return parseRefusal(error, REASONS)
}

export const aiQueryOptions = queryOptions({
  queryKey: ['settings', 'ai'],
  queryFn: () => apiGet<AiSettings>('/settings/ai'),
})

/** `api_key` 不送或 `null` 是留著原本的；空字串是清掉（只有「移除 key」該送）。 */
export function saveAi(body: AiSettingsBody): Promise<AiSettings> {
  return apiPut<AiSettings>('/settings/ai', body)
}

/** 用**存著的**設定打三次請求。端點說不行也是 200，結果在 `failure` 與 `tools`。 */
export function runAiTest(): Promise<AiTest> {
  return apiPost<AiTest>('/settings/ai/test')
}

/** 問端點有哪些模型。列不出來時 `models` 是 `null`，退回手填。 */
export function listAiModels(): Promise<AiModels> {
  return apiGet<AiModels>('/settings/ai/models')
}

/** 用量頁（M5 票 13）：今天往前幾天的彙總。 */
export type AiUsage = Schemas['AiUsageOut']

export type UsageTally = Schemas['UsageTallyOut']

/** 一列 `ai_calls` 是誰叫的。 */
export type AiCallOrigin = Schemas['AiCallOrigin']

/** 期間只有後端的 `UsageDays` 那幾種。 */
export type UsagePeriod = Schemas['UsageDays']

/** 照切換列的先後。少一種或多一種都是編譯錯誤（同上面的 `REASONS`）。 */
const PERIODS: Record<UsagePeriod, true> = { 7: true, 30: true, 90: true }

export const USAGE_PERIODS: readonly UsagePeriod[] = (Object.keys(PERIODS) as `${UsagePeriod}`[])
  .map((days) => Number(days) as UsagePeriod)
  .sort((a, b) => a - b)

export const DEFAULT_USAGE_PERIOD: UsagePeriod = 30

/** 網址上的 `days`：認得的才收，其餘是 `undefined`（落回預設）。 */
export function usagePeriodOf(value: unknown): UsagePeriod | undefined {
  return USAGE_PERIODS.find((days) => days === Number(value))
}

export function aiUsageQueryOptions(days: UsagePeriod) {
  return queryOptions({
    queryKey: ['settings', 'ai', 'usage', days],
    queryFn: () => apiGet<AiUsage>(`/settings/ai/usage?days=${days}`),
  })
}
