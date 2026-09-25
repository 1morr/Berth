import type { AuditReviewRow, ReviewRow } from '../api/review'

/** 佇列上畫成一格的東西：單獨的一列，或同一個 RSS Series / 同一個 Job 的一組 audit（M3 票 05、13）。 */
export type ReviewEntry =
  { kind: 'row'; row: ReviewRow } | { kind: 'group'; key: string; rows: AuditReviewRow[] }

/**
 * 一列 audit 屬於哪一組。**有 RSS Series 的先用它**（M3 票 13）：補舊集一次送十幾筆下載、一集一個
 * Job，以 Job 分組等於不分；而第一批要人看的正是這一個 Series 的季號與集數。其餘照同一個 Job。
 * 沒有 Job 的（`rebuild-ledger` 長回來的帳本列）不分組。
 */
function groupKey(row: AuditReviewRow): string | null {
  if (row.series !== null) return `series:${row.series.id}`
  return row.job_hash !== '' ? `job:${row.job_hash}` : null
}

/**
 * 這一組只有一列時還要不要畫成組。**還沒確認的 RSS Series 要**：組上那顆「全部確認」除了清旗標，還把
 * Series 標成確認過（之後它的 medium 不再進來），與單列的「確認」不是同一件事——第一批只有一集時少了
 * 它，那個 Series 就確認不了。其餘的只有一列就是一列（下面那一句）。
 */
function evenAlone(group: readonly AuditReviewRow[]): boolean {
  return group[0]?.reason.code === 'first_batch'
}

/**
 * 把同一組的 audit 收在一起，**位置是它第一列出現的地方**：後端排好的順序不動（前端不重排），
 * 只是同一組的後幾列往前併。只有一列的組就是一列——一顆「全部確認」只確認一個，與它自己那顆沒有兩樣；
 * 還沒確認的 RSS Series 例外（`evenAlone`）。
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
    if (key === null || group === undefined || (group.length < 2 && !evenAlone(group))) {
      entries.push({ kind: 'row', row })
    } else if (!placed.has(key)) {
      placed.add(key)
      entries.push({ kind: 'group', key, rows: group })
    }
  }
  return entries
}
