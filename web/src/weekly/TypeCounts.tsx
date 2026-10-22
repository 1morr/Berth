import { useTranslation } from 'react-i18next'

import type { Issue } from '../api/issues'

/**
 * 「缺集 ×2、無主目錄」：型別的詞與 `/issues` 同一組（`issues.typeLabel`），一件的不寫 ×1。
 * 多的在前，同數量照後端給的順序。
 */
export function TypeCounts({ counts }: { counts: Record<string, number> }) {
  const { t } = useTranslation()
  const entries = Object.entries(counts)
    .filter(([, count]) => count > 0)
    .sort(([, left], [, right]) => right - left)
  if (entries.length === 0) return null

  const parts = entries.map(([type, count]) => {
    // 鍵是後端的 `IssueType`，OpenAPI 裡 `dict[IssueType, int]` 只剩 `string`；詞表少一種是 `issues.typeLabel` 的型別在擋。
    const label = t(`issues.typeLabel.${type as Issue['type']}`)
    return count > 1 ? t('weekly.typeTimes', { label, times: count }) : label
  })
  return (
    <p className="value wrap-anywhere text-xs text-ink-dim">{parts.join(t('weekly.typeJoin'))}</p>
  )
}
