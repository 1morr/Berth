import { useTranslation } from 'react-i18next'

import { SIGNAL_FILL } from './signal'

/**
 * 「N 個待確認」：medium 自動入庫、還要人看一眼的檔案數（brief §6.5、PRODUCT 原則 3）。
 *
 * 貼在狀態色塊旁邊而不是取代它：狀態是綠色的「已入庫」，而這是另一件事（DESIGN.md 的 The
 * Needs-You Floats Up Rule）。`assigned` 就是「需要你」。沒有待確認的檔案時什麼都不畫。
 */
export function AuditChip({ count, compact = false }: { count: number; compact?: boolean }) {
  const { t } = useTranslation()
  if (count <= 0) return null

  return (
    <span
      className={`label shrink-0 ${compact ? 'px-1.5 py-0.5' : 'px-2 py-1.5'} ${SIGNAL_FILL.assigned}`}
    >
      {t('common.audits', { count })}
    </span>
  )
}
