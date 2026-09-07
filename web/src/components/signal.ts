/**
 * 法定色：整個 app 只有四個信號色，每個顏色只有一個意思，紅色永遠只代表阻擋
 * （`.impeccable/surfaces/` 的 direction contract）。這是設計系統的一部分，
 * 不專屬設定精靈——健康頁與之後的頁面用同一組。
 *
 * `neutral` 不是信號：它表示「不需要你，也還沒完成」。
 */
export type Signal = 'neutral' | 'assigned' | 'working' | 'secured' | 'blocked'

/** 塗裝色塊的類名。色塊填滿整格，不是描邊。 */
export const SIGNAL_FILL: Record<Signal, string> = {
  neutral: 'bg-deck text-ink',
  assigned: 'bg-assigned text-on-signal',
  working: 'bg-working text-on-signal',
  secured: 'bg-secured text-on-signal',
  blocked: 'bg-blocked text-on-signal',
}
