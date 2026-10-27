import { queryOptions } from '@tanstack/react-query'

import { apiDelete, apiGet, apiPost, apiPut } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { Schemas } from './schemas'

/**
 * AI provider 的設定（M5 票 09，只有 admin）：兩種接口各自的 base URL、key、模型，開關與 Tavily key。
 * **key 只往後端去、永遠不回來**：回來的只有 `has_key` / `has_tavily_key`。
 */

export type AiSettings = Schemas['AiOut']

export type AiEndpoint = Schemas['AiEndpointOut']

export type AiProvider = Schemas['AiProvider']

export type AiProbeFailure = Schemas['AiProbeFailure']

export type AiTest = Schemas['AiTestOut']

export type AiSecret = Schemas['AiSecret']

export type AiRefusal = Schemas['AiRefusal']

/** 執行期認得的那幾種。少一種或多一種都是編譯錯誤（同 `api/notify.ts`）。 */
const REASONS: ReasonSet<AiRefusal> = {
  base_url_invalid: true,
  key_missing: true,
  model_missing: true,
}

/** 認不得的理由是 `null`，畫面照請求為什麼沒成說（`RequestFailed`）。 */
export function aiRefusalOf(error: unknown): Refusal<AiRefusal> | null {
  return parseRefusal(error, REASONS)
}

export const aiQueryOptions = queryOptions({
  queryKey: ['settings', 'ai'],
  queryFn: () => apiGet<AiSettings>('/settings/ai'),
})

/** 存表單上那一種接口並設成現在用的。key 欄空著（`null`）是不動。 */
export function saveAi(body: Schemas['AiIn']): Promise<AiSettings> {
  return apiPut<AiSettings>('/settings/ai', body)
}

/** 照表單打一次最小呼叫，不存。服務拒絕也是 200，結果在 `ok` 與 `failure`。 */
export function testAi(body: Schemas['AiTestIn']): Promise<AiTest> {
  return apiPost<AiTest>('/settings/ai/test', body)
}

/** 清掉一把 key。清的是現在用的接口的 key 時，後端一併關掉 AI。 */
export function forgetAiKey(secret: AiSecret): Promise<AiSettings> {
  return apiDelete<AiSettings>(`/settings/ai/keys/${secret}`)
}
