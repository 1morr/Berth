import { queryOptions } from '@tanstack/react-query'

import { apiGet, apiPut } from './client'
import { parseRefusal, type ReasonSet, type Refusal } from './refusal'
import type { Schemas } from './schemas'

/**
 * AI 用量頁（只有 admin）與每一輪的步驟頁（M5 票 21，`.scratch/m5/usage-and-run-shape.md`）。
 *
 * **不知道的不當 0**：快取讀寫與費用是 `{known, unknown}`——知道的加總與幾次呼叫不知道。
 */

export type Usage = Schemas['UsageOut']

export type DayUsage = Schemas['DayUsageOut']

export type SpendAlert = Schemas['SpendAlertOut']

export type Run = Schemas['RunOut']

export type RunStep = Schemas['RunStepOut']

export type StepTool = Schemas['StepToolOut']

export type AiStopReason = Schemas['AiStopReason']

export type AiToolOutcome = Schemas['AiToolOutcome']

export type AiRunRefusal = Schemas['AiRunRefusal']

const REASONS: ReasonSet<AiRunRefusal> = { run_missing: true }

export function runRefusalOf(error: unknown): Refusal<AiRunRefusal> | null {
  return parseRefusal(error, REASONS)
}

export const usageQueryOptions = queryOptions({
  queryKey: ['settings', 'usage'],
  queryFn: ({ signal }) => apiGet<Usage>('/settings/usage', { signal }),
})

/** 存每日提醒值（美元）；`null` 是不提醒。只提醒，不停用 AI。 */
export function saveSpendAlert(dailyUsd: number | null): Promise<Schemas['SpendAlertSetOut']> {
  return apiPut('/settings/usage/alert', { daily_usd: dailyUsd })
}

/** 還在跑的那一輪每 2 秒重問，停了就不再問。 */
export function runQueryOptions(runId: string) {
  return queryOptions({
    queryKey: ['agent', 'runs', runId],
    queryFn: ({ signal }) => apiGet<Run>(`/agent/runs/${encodeURIComponent(runId)}`, { signal }),
    refetchInterval: (query) => (query.state.data?.stop_reason === null ? 2000 : false),
  })
}
