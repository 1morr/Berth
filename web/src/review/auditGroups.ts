import type { AuditReviewRow, ReviewRow } from '../api/review'

/** 佇列上畫成一格的東西：單獨的一列，或同一個 Job 的一組 audit（M3 票 05）。 */
export type ReviewEntry =
  { kind: 'row'; row: ReviewRow } | { kind: 'group'; key: string; rows: AuditReviewRow[] }

/**
 * 一列 audit 屬於哪一組。現在只有同一個 Job；票 13 的同一個 RSS Series 是另一種鍵，加在這裡
 * （有 RSS Series 的先用它）。沒有 Job 的（`rebuild-ledger` 長回來的帳本列）不分組。
 */
function groupKey(row: AuditReviewRow): string | null {
  return row.job_hash !== '' ? `job:${row.job_hash}` : null
}

/**
 * 把同一組的 audit 收在一起，**位置是它第一列出現的地方**：後端排好的順序不動（前端不重排），
 * 只是同一組的後幾列往前併。只有一列的組就是一列——一顆「全部確認」只確認一個，與它自己那顆沒有兩樣。
 */
export function groupAudits(rows: readonly ReviewRow[]): ReviewEntry[] {
  const members = new Map<string, AuditReviewRow[]>()
  for (const row of rows) {
    const key = row.kind === 'audit' ? groupKey(row) : null
    if (row.kind === 'audit' && key !== null) members.set(key, [...(members.get(key) ?? []), row])
  }
  const entries: ReviewEntry[] = []
  const placed = new Set<string>()
  for (const row of rows) {
    const key = row.kind === 'audit' ? groupKey(row) : null
    const group = key !== null ? members.get(key) : undefined
    if (key === null || group === undefined || group.length < 2) {
      entries.push({ kind: 'row', row })
    } else if (!placed.has(key)) {
      placed.add(key)
      entries.push({ kind: 'group', key, rows: group })
    }
  }
  return entries
}
