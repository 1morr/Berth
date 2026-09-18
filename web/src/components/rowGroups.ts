/** 一組：同一個鍵的那幾列，與「裡面有沒有一列需要人」。 */
export type RowGroup<T> = { key: string; rows: T[]; held: boolean }

/**
 * 依決定分組（檔案與版本、下載列的計劃，`.scratch/m1.5/long-lists-shape.md`）。
 *
 * 組照第一次出現的順序、組裡照原本的順序；**有一列需要人的組排到最前面**（The Needs-You Floats Up Rule）——
 * 收起來的一整份清單，第一眼看到的要是等你的那幾組。
 */
export function groupRows<T>(
  rows: readonly T[],
  key: (row: T) => string,
  held: (row: T) => boolean,
): RowGroup<T>[] {
  const groups = new Map<string, RowGroup<T>>()
  for (const row of rows) {
    const name = key(row)
    const group = groups.get(name) ?? { key: name, rows: [], held: false }
    group.rows.push(row)
    group.held ||= held(row)
    groups.set(name, group)
  }
  const all = [...groups.values()]
  return [...all.filter((group) => group.held), ...all.filter((group) => !group.held)]
}
