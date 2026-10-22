/** 一個 Issue 型別計數表的加總。 */
export function sumCounts(counts: Record<string, number>): number {
  return Object.values(counts).reduce((sum, count) => sum + count, 0)
}
