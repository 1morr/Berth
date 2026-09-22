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

/**
 * 同一組色塊，但「已繫上」不塗漆——DESIGN.md 的 **The Usual Stays Unpainted Rule**
 * （常態不塗漆，例外才塗）用在狀態色塊上（票 03 第 16 條）。
 *
 * 健康頁全綠時同一顆綠章在一千像素裡出現八次：泊位板四格、三張服務卡、Route 總結，
 * 再加上每條 Route 一顆。**板子是那一頁的第一個 viewport，它負責回答「有沒有紅的」**；
 * 板子底下的每一塊再塗一次綠只是把同一句話說八遍，反而讓真的紅的那一塊不顯眼。
 * 所以板子留漆，底下的列與卡片只在**不是全好**的時候塗——沒有塗漆的那些仍然帶著文字
 * （「已繫上」），狀態不只靠顏色（PRODUCT.md）。
 *
 * 常態那一格就是 `neutral` 本人，不另外抄一份類名。
 */
export const UNPAINTED_FILL: Record<Signal, string> = {
  ...SIGNAL_FILL,
  secured: SIGNAL_FILL.neutral,
}
