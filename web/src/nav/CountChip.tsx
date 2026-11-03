import { SIGNAL_FILL } from '../components/signal'

/**
 * 導覽項與區塊分頁上「有幾件在等你」的那一塊（M5.5 票 07）。`assigned` 是「現在需要你」
 * （The Needs-You Floats Up Rule），所以 0 件時整塊不畫，不是畫一個 0。
 *
 * 只是看得見的那一半（`aria-hidden`）：聽得見的那一句由連結的 `aria-label` 說（`sections.ts` 的 `countedName`）。
 * 不用 sr-only 補字：它和標籤之間的空白在不同的無障礙樹實作裡留不留得住不一定（jsdom 念成「待處理3 件」）。
 */
export function CountChip({ count }: { count: number | undefined }) {
  if (!count) return null
  return (
    // `.value` 不是 `.label`：數字不要刻度與大寫字距。`ml-2` 而不是父層的 `gap`：`.label` 的刻度是
    // `::before`，在 flex 裡會變成一個 flex 項，`gap` 會把它和標籤拆開。
    <span
      aria-hidden="true"
      className={`value ml-2 px-1.5 py-0.5 text-xs font-semibold ${SIGNAL_FILL.assigned}`}
    >
      {count}
    </span>
  )
}
