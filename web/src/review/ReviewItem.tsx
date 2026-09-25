import type { ReviewRow } from '../api/review'
import type { Said } from './useConfirmAudits'
import { AuditRow } from './AuditRow'
import { DuplicateRow } from './DuplicateRow'
import { PlanRow } from './PlanRow'
import { UnmatchedRow } from './UnmatchedRow'

/**
 * 審核佇列上的一件事畫成哪個元件（`.scratch/m2/review-shape.md`）。`/review` 與媒體庫頁的「待審 / 對不到」
 * （M2 票 14）**畫的是同一個元件**：同一件事在兩頁長得一樣、按的是同一顆鍵。
 *
 * **窮舉**：後端把新的 `kind` 加進聯集時，少一支是 `tsc` 的事。`onDone` 收的是按完之後要念出來的那一句
 * （`shown`：一次動了好幾列時也畫出來）。
 */
export function ReviewItem({ row, onDone }: { row: ReviewRow; onDone: Said }) {
  switch (row.kind) {
    case 'plan':
      return <PlanRow row={row} onDone={onDone} />
    case 'audit':
      return <AuditRow row={row} onDone={onDone} />
    case 'unmatched':
      return <UnmatchedRow row={row} onDone={onDone} />
    case 'duplicate':
      return <DuplicateRow row={row} onDone={onDone} />
  }
}
