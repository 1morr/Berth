/**
 * 牆的欄數。媒體庫的牆（票 13）是同一座堆場的盤點表，格子必須與這裡對得齊——
 * 所以斷點只有這一份。
 */
export const WALL_GRID = 'grid grid-cols-2 gap-0 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6'

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
