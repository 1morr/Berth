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

export type AiModels = Schemas['AiModelsOut']

export type AiSecret = Schemas['AiSecret']

export type AiReasoning = Schemas['AiReasoning']

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

/**
 * 模型欄沒按「取得模型」之前的建議（M5.5 票 02）：本機價目表照這個網址認出的那一家。不帶 key、
 * 後端也不連外，所以跟著表單上的網址換。
 */
export function aiSuggestionsQueryOptions(provider: AiProvider, baseUrl: string) {
  return queryOptions({
    queryKey: ['settings', 'ai', 'models', provider, baseUrl],
    queryFn: () =>
      apiGet<AiModels>(
        `/settings/ai/models?${new URLSearchParams({ provider, base_url: baseUrl })}`,
      ),
    // 本機表跟著 Berth 的版本走，開著頁面時不會變。
    staleTime: Infinity,
  })
}

/**
 * 表單上的端點與模型，推理程度怎麼送（M5.5 票 17、17b）：`applies` 假的是 Berth 四級都不送，
 * `off_sends_nothing` 真的是認不得的相容閘道「關」不送。後端只看 model profile 與網址，不帶 key、不連外。
 */
export function aiReasoningQueryOptions(provider: AiProvider, baseUrl: string, model: string) {
  return queryOptions({
    queryKey: ['settings', 'ai', 'reasoning', provider, baseUrl, model],
    queryFn: () =>
      apiGet<Schemas['AiReasoningOut']>(
        `/settings/ai/reasoning?${new URLSearchParams({ provider, base_url: baseUrl, model })}`,
      ),
    // profile 跟著 Berth 的版本走，開著頁面時不會變。
    staleTime: Infinity,
    enabled: model !== '',
  })
}

/** 「取得模型」：向表單上的端點問，不存。問不到也是 200，退回本機表並帶著原因。 */
export function fetchAiModels(body: Schemas['AiModelsIn']): Promise<AiModels> {
  return apiPost<AiModels>('/settings/ai/models', body)
}

/** 清掉一把 key。清的是現在用的接口的 key 時，後端一併關掉 AI。 */
export function forgetAiKey(secret: AiSecret): Promise<AiSettings> {
  return apiDelete<AiSettings>(`/settings/ai/keys/${secret}`)
}
