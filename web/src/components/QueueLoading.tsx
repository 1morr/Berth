/**
 * 排隊清單（`/issues`、`/review`、媒體庫的待審 / 對不到）讀取中的佔位。**兩列靜態方塊，沒有動畫**——這個世界
 * 沒有骨架屏的脈動（DESIGN.md）。
 *
 * 高度與真的一列相近，資料回來時版面不跳（票 12 的 CLS 是同一件事）。寬度跟著所在的那一欄，由呼叫端給
 * （`className`）。
 */
export function QueueLoading({ className = '' }: { className?: string }) {
  return (
    <div className={`grid gap-3 ${className}`} aria-hidden="true">
      <div className="h-24 border-2 border-rule bg-well" />
      <div className="h-24 border-2 border-rule bg-well" />
    </div>
  )
}
