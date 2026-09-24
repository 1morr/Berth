import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import type { AuditReviewRow } from '../api/review'
import { ConfirmAction, Notice } from '../components/controls'
import { useConfirmAudits, type Said } from './useConfirmAudits'

/**
 * 「已入庫，等你看一眼」那一段標題列上的「全部確認」（M3 票 05，使用者 2026-09-24 試跑時拍板：一包 12 集
 * 全是 medium 要逐列按）。
 *
 * **範圍是畫面上列出的那些**，而且在確認**展開的那一刻**凍結：使用者讀到「這 N 個」之後佇列才重問（切回視窗、
 * 別的列按完）進來的 audit，不會被順手確認掉，那一句件數也不會悄悄改掉。先就地確認並說出件數（DESIGN.md
 * 就地確認）——它橫跨好幾筆下載，按之前要看得到自己在確認多少個。只作用於 audit：同一段的重複版本要逐件
 * 判斷，不在內。
 */
export function AuditSectionConfirm({
  rows,
  onDone,
}: {
  rows: readonly AuditReviewRow[]
  onDone: Said
}) {
  const { t } = useTranslation()
  const { confirm, pending, failed } = useConfirmAudits(onDone)
  const [frozen, setFrozen] = useState<readonly number[]>([])
  const count = frozen.length

  return (
    <div className="grid justify-items-start gap-2">
      <ConfirmAction
        label={t('review.audit.confirmAll')}
        confirmLabel={t('review.audit.confirmSectionAction', { count })}
        warning={t('review.audit.confirmSection', { count })}
        pending={pending}
        pendingLabel={t('review.audit.working')}
        onOpen={() => setFrozen(rows.map((row) => row.ref))}
        onConfirm={() => confirm(frozen)}
      />
      {failed !== null && (
        <Notice signal="blocked" label={t('common.failed')}>
          {failed}
        </Notice>
      )}
    </div>
  )
}
