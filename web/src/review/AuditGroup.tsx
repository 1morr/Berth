import { useTranslation } from 'react-i18next'

import type { AuditReviewRow } from '../api/review'
import { GhostButton } from '../components/controls'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { whenText } from '../components/queueText'
import { displayRound } from '../i18n/displayRound'
import { JobLink } from '../jobs/JobLink'
import { AuditRow } from './AuditRow'
import { groupLead, leadText } from './leadReason'
import { useConfirmAudits, type Said } from './useConfirmAudits'

/**
 * 同一個 Job 的幾個 audit，一組一顆「全部確認」（M3 票 05，使用者 2026-09-24 拍板：一包芙莉蓮的 11 個特典
 * 本來要逐一按）。
 *
 * **也是一列**（`QueueRow`）：標題是作品、一句話說整組為什麼是 medium——組內原因相同就說一次，不同就說
 * 不只一種（`groupLead`）。成員收在展開裡，每一個仍然能單獨確認或撤銷（撤銷是逐列的，確認錯了一個要能
 * 只拿掉那一個）。
 *
 * 「全部確認」**不就地確認**：同單列的「確認」，它只清旗標、檔案不動，錯了逐列撤銷得回來。整段的那一顆
 * 才要（`AuditSectionConfirm`）——它的範圍橫跨好幾筆下載，按之前要看得到件數。
 */
export function AuditGroup({ rows, onDone }: { rows: readonly AuditReviewRow[]; onDone: Said }) {
  const { t, i18n } = useTranslation()
  const { confirm, pending, failed } = useConfirmAudits(onDone)

  const [first] = rows
  if (first === undefined) return null
  const count = rows.length
  const lead = groupLead(rows.map((row) => row.reasons))
  const title = displayRound(i18n.language, { 'zh-Hant': first.title, en: first.title_en })
  // 等得最久的那一個說了這一組等了多久。
  const oldest = rows.reduce((earliest, row) => (row.at < earliest ? row.at : earliest), first.at)

  return (
    <QueueRow
      label={t('review.audit.label')}
      heading="h3"
      title={title || first.job_name || first.job_hash}
      sentence={
        lead.kind === 'same'
          ? t('review.audit.group.same', { count, lead: leadText(t, lead.reason) })
          : t(`review.audit.group.${lead.kind}`, { count })
      }
      when={t('review.audit.importedAt', { value: whenText(oldest, i18n.language) })}
      refusal={failed}
      details={
        <DetailLine term={t('review.audit.job')}>
          <JobLink hash={first.job_hash}>{first.job_name || first.job_hash}</JobLink>
        </DetailLine>
      }
      members={
        <ul className="mt-2 grid gap-2">
          {rows.map((row) => (
            <li key={row.ref} className="min-w-0">
              <AuditRow row={row} onDone={onDone} member={{ quiet: lead.kind !== 'mixed' }} />
            </li>
          ))}
        </ul>
      }
    >
      <GhostButton
        type="button"
        disabled={pending}
        onClick={() => confirm(rows.map((row) => row.ref))}
      >
        {pending ? t('review.audit.working') : t('review.audit.confirmAll')}
      </GhostButton>
    </QueueRow>
  )
}
