import type { ParseKeys } from 'i18next'

import type { AiStopReason, AiToolOutcome } from '../api/usage'

/** 停止原因的說法；`running` 是還在跑（`stop_reason` 是 `null`）。少一種是編譯錯誤。 */
export const STOP_TEXT = {
  completed: 'usage.stop.completed',
  request_limit: 'usage.stop.request_limit',
  token_limit: 'usage.stop.token_limit',
  repeated_call: 'usage.stop.repeated_call',
  ping_pong: 'usage.stop.ping_pong',
  no_progress: 'usage.stop.no_progress',
  circuit_open: 'usage.stop.circuit_open',
  error: 'usage.stop.error',
  cancelled: 'usage.stop.cancelled',
  running: 'usage.stop.running',
} as const satisfies Record<AiStopReason | 'running', ParseKeys>

/** 一次工具呼叫的結果。少一種是編譯錯誤。 */
export const OUTCOME_TEXT = {
  ok: 'usage.outcome.ok',
  warned: 'usage.outcome.warned',
  blocked: 'usage.outcome.blocked',
  aborted: 'usage.outcome.aborted',
  refused: 'usage.outcome.refused',
  failed: 'usage.outcome.failed',
} as const satisfies Record<AiToolOutcome, ParseKeys>
