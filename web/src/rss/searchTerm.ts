/**
 * 綁定時搜尋框預填的字：從發佈名讀出作品名（`.scratch/m3/rss-shape.md` §3）。
 *
 * 字幕組的發佈名多半是 `[組名] 中文名 / 英文或羅馬字名 - 12 [tags…]`。去掉開頭的 `[組名]`
 * 與 ` - 集號` 之後的一切，有 ` / ` 時取**最後一段**：TMDB 的英文標題多半與它相符，而第一段常是
 * 簡體譯名，搜不到繁中那一輪的標題。沒有 ` / ` 就是整段（`[ANi] Re：从零开始… 第四季 - 18`）。
 * 讀不出來時回原樣——那一格使用者本來就要核對或改。
 */
export function searchTerm(title: string): string {
  const withoutGroup = title.replace(/^\s*(?:\[[^\]]*\]\s*)+/, '')
  const [name = ''] = withoutGroup.split(/\s+-\s+\d/)
  const parts = name.split(' / ').map((part) => part.trim())
  const picked = parts.findLast((part) => part !== '') ?? ''
  return picked || title.trim()
}
