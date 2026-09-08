import type { ServiceHealth } from '../api/health'
import type { ServiceKind } from '../api/schemas'
import type { Signal } from '../components/signal'

/**
 * 一項健康檢查怎麼讀（票 10）。
 *
 * 五種狀態，四個信號色的規則不變（每個顏色只有一個意思）：
 *
 * - `secured` 已繫上——連得上而且沒有漂移。
 * - `assigned` 需要你——服務好好的，但 Berth 的建議設定被改掉了（brief §16.3）。
 *   **不是紅的**：東西還在動，只是有一天會出錯。
 * - `blocked` 阻擋——連不上、憑證不對、版本太舊。紅色只代表阻擋。
 * - `neutral` 尚未檢查 / 尚未接上——索引站那一步可以跳過（plan §9.3），跳過的人
 *   不該永遠看到一盞紅燈。
 */

export type HealthState = 'ok' | 'drift' | 'failed' | 'unknown' | 'unconfigured'

export function serviceState(row: ServiceHealth): HealthState {
  // **順序有意義**：迴圈第一輪跑之前每一項都還沒被檢查過，而那時候 `configured` 也還是預設的
  // `false`——先判 `configured` 會對三個已經接好的服務說「到設定精靈接它」。
  if (row.checked_at === null) return 'unknown'
  if (!row.configured) return 'unconfigured'
  if (row.status === 'failed') return 'failed'
  if (row.status === 'unknown') return 'unknown'
  return row.drift.length > 0 ? 'drift' : 'ok'
}

export const STATE_SIGNAL = {
  ok: 'secured',
  drift: 'assigned',
  failed: 'blocked',
  unknown: 'neutral',
  unconfigured: 'neutral',
} as const satisfies Record<HealthState, Signal>

export const STATE_LABEL = {
  ok: 'health.state.ok',
  drift: 'health.state.drift',
  failed: 'health.state.failed',
  unknown: 'health.state.unknown',
  unconfigured: 'health.state.unconfigured',
} as const satisfies Record<HealthState, string>

/**
 * 這一項紅了要做什麼（PRODUCT.md 原則 4：失敗要說得出下一步）。
 *
 * 分兩種是因為修法完全不同：**套件內**的服務是 compose 起的，答案幾乎都是「那個容器
 * 不在了」，所以給指令；**既有**的服務是使用者自己的，Berth 只知道位址與憑證變了，
 * 所以送他回精靈的連線表單。
 */
export function serviceFix(row: ServiceHealth): 'bundled' | 'existing' | 'unconfigured' {
  if (!row.configured) return 'unconfigured'
  return row.origin === 'bundled' ? 'bundled' : 'existing'
}

/**
 * 套件內服務掛掉時的三條指令。順序就是排查順序：還在嗎、起來、它自己說了什麼。
 *
 * `kind` 直接當 compose 的服務名——CONTEXT.md 的 **Service** 就是這麼定的（「字串同時是
 * compose 的服務名」），所以不需要一張對照表。
 */
export function composeCommands(kind: ServiceKind): readonly string[] {
  return [
    `docker compose ps ${kind}`,
    `docker compose up -d ${kind}`,
    `docker compose logs --tail=50 ${kind}`,
  ]
}
