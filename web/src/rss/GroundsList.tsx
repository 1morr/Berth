import { useTranslation } from 'react-i18next'

import type { BindReason } from '../api/rss'
import { groundText } from './grounds'

/** 一串自動綁定的理由，一條一行。前面那一句（`lead`）說這串是依據還是為什麼。 */
export function Grounds({ lead, reasons }: { lead: string; reasons: readonly BindReason[] }) {
  const { t, i18n } = useTranslation()
  if (reasons.length === 0) return null
  return (
    <div className="grid gap-0.5 text-xs text-ink-dim">
      <p>{lead}</p>
      <ul className="grid list-disc gap-0.5 pl-4">
        {reasons.map((reason, index) => (
          // 參數是原文（標題、日期、Route 名），但整句是翻譯的，不拆成 `.value` 片段。
          <li key={`${reason.code}-${index}`} className="max-w-prose wrap-anywhere">
            {groundText(t, reason, i18n.language)}
          </li>
        ))}
      </ul>
    </div>
  )
}
