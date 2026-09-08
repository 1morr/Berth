import type { StepStatus } from '../api/setup'
import type { Signal } from '../components/signal'

/** 一條纜繩的狀態怎麼讀。三個泊位共用，所以住在元件外面（plan §9.3）。 */

export const STATUS_LABEL = {
  ok: 'status.ok',
  skipped: 'status.skipped',
  failed: 'status.failed',
  running: 'status.running',
  pending: 'status.pending',
} as const satisfies Record<StepStatus, string>

/** 步驟狀態 → 信號。`skipped` 與 `ok` 同色：兩者都代表「這一步的事完成了」。 */
export const STATUS_SIGNAL = {
  ok: 'secured',
  skipped: 'secured',
  failed: 'blocked',
  running: 'working',
  pending: 'neutral',
} as const satisfies Record<StepStatus, Signal>

/** 這一步做完了沒。`skipped` 也算完成——它的意思是「已經是想要的樣子」。 */
export function isSettled(status: StepStatus): boolean {
  return status === 'ok' || status === 'skipped'
}
