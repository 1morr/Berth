/**
 * 牆的欄數。媒體庫的牆（票 13）是同一座堆場的盤點表，格子必須與這裡對得齊——
 * 所以斷點只有這一份。窄版兩欄——一欄會讓一屏只看得到一部作品，而牆的工作是掃視。
 *
 * 線由每一格自己的 `border-2` 畫，**不是**把整塊網格塗成 `rule` 再用 `gap-px` 透出來
 * （泊位板是那樣做的）。理由是那塊板永遠是四格滿的，而牆的格數是給多少算多少：
 * 塗底的話，只搜到一部作品時整排空欄會變成一塊灰色的板子——探索牆實跑第一輪就是這個樣子。
 */
export const WALL_GRID = 'grid grid-cols-2 gap-0 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6'

/**
 * 媒體庫牆再加這一個：**卡片裡有就地確認**（`WatchToggle`）的只有那一面牆，展開時同排的每一格
 * 會被 grid 預設的 `stretch` 一起拉長——390px 上量到同排多出約 300px 空白，而位移正好發生在
 * 使用者要決定一個清掉就回不來的動作時（The Failure Expands In Place Rule，票 11 的 critique）。
 *
 * 代價是**同排的下緣不再對齊**：標題兩行的格子比一行的高一截，`JellyfinLine` 是釘在卡片底部的
 * （DESIGN.md 牆卡片那一節）。兩害相權取這一個；記在 DESIGN.md 的 Known contradictions。
 * 探索牆、繼續觀看與觀看區的集沒有就地確認，所以不加。
 */
export const WALL_GRID_CONFIRMABLE = `${WALL_GRID} items-start`

/**
 * 同一份欄數收成一行（繼續觀看與下一集，M1.5 票 07）：第幾格在哪個寬度以上才出現，第 7 格起藏著。
 * **改 `WALL_GRID` 的斷點就要一起改這裡**——Tailwind 的類名必須是字面值，推不出來。
 */
export function oneRowOnly(index: number): string {
  return (
    ['', '', 'hidden sm:block', 'hidden lg:block', 'hidden xl:block', 'hidden xl:block'][index] ??
    'hidden'
  )
}

/** `count` 格在哪個寬度以上一行就放得下（「全部 N 項」在那裡不畫）；兩格以下哪裡都放得下，是 `null`。 */
export function fitsOneRowFrom(count: number): string | null {
  if (count <= 2) return null
  if (count <= 3) return 'sm:hidden'
  if (count <= 4) return 'lg:hidden'
  if (count <= 6) return 'xl:hidden'
  return ''
}
