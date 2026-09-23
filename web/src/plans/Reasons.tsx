import { useTranslation } from 'react-i18next'

import type { ItemReason } from '../api/plans'
import { reasonText } from './reasonText'

/**
 * 一列的理由，逐條一行（brief §6.5）。計劃表格、審核佇列的 Plan 與 audit 兩類共用。
 *
 * 句子是翻譯過的散文，所以用系統字而不是 `.value`；參數裡的檔名與路徑會很長，`wrap-anywhere`
 * 讓它們在窄版上換行而不是把整頁撐寬。
 */
export function Reasons({ reasons }: { reasons: readonly ItemReason[] }) {
  const { t } = useTranslation()
  if (reasons.length === 0) return null

  return (
    <ul className="grid gap-0.5">
      {reasons.map((reason, index) => (
        // 同一個 code 可以出現兩次（兩條標題比對），所以鍵帶位置。
        <li key={`${reason.code}:${index}`} className="text-xs wrap-anywhere text-ink-dim">
          {reasonText(t, reason)}
        </li>
      ))}
    </ul>
  )
}
