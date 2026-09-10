/**
 * 值與值之間的中點分隔。
 *
 * `aria-hidden`：它是排版不是內容，不該被逐個念出來。DESIGN.md 的「不用字元當裝飾標記」
 * 說的是**會進無障礙名稱**的那種標記（`▸`、`•`、emoji）；這一個從無障礙樹上消失了，
 * 而它必須是行內字元——CSS 畫的刻度跟不上一行會換行的值列表（`::after` 定位得靠一個
 * 固定的盒子，而這幾格的寬度由內容決定）。已記進 DESIGN.md 的 Known contradictions。
 *
 * 一份而不是每個列表各寫一次：票 08 的結果表與票 09 的下載列表用的是同一個東西。
 */
export function Dot() {
  return (
    <span aria-hidden="true" className="text-ink-dim">
      ·
    </span>
  )
}
