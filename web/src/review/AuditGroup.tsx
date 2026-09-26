import { useTranslation } from 'react-i18next'

import type { AuditReviewRow } from '../api/review'
import { GhostButton } from '../components/controls'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { whenText } from '../components/queueText'
import { displayRound } from '../i18n/displayRound'
import { JobLink } from '../jobs/JobLink'
import { firstBatchAskText } from '../rss/firstBatchAsk'
import { seriesValuesText } from '../rss/seriesValues'
import { AuditRow } from './AuditRow'
import { groupLead, leadText } from './leadReason'
import { useConfirmAudits, type Said } from './useConfirmAudits'

/**
 * 同一個 RSS Series 或同一個 Job 的幾個 audit，一組一顆「全部確認」（M3 票 05，使用者 2026-09-24 拍板：
 * 一包芙莉蓮的 11 個特典本來要逐一按；票 13：RSS Series 的第一批）。
 *
 * **也是一列**（`QueueRow`）：標題是作品、一句話說整組為什麼在這裡——組內原因相同就說一次，不同就說
 * 不只一種（`groupLead`）。成員收在展開裡，每一個仍然能單獨確認、撤銷或改季集（撤銷是逐列的，確認錯了
 * 一個要能只拿掉那一個）。
 *
 * **RSS Series 的第一批**（`series.confirmed = false`）另說一句：信心 high 的也在這裡，要人看的是季號與
 * 集數對不對，所以那一句不是 medium 的原因，而是**在問什麼**——哪幾集、季集怎麼讀出來的（M4 票 11，
 * `firstBatchAskText`）。`ask` 是 `null` 的那一種——等人的只剩特典或字幕、沒有一集正片可說——退回件數
 * 那一句。展開說出是哪一個 Series（它的名字看得出字幕組）與它現在的季號、偏移；組的那一顆是「確認整個
 * Series」，打 Series 那一支（`useConfirmAudits`），之後它的 medium 不再進來。
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
  // 以 Series 分組時整組同一個 Series（`auditGroups`），以 Job 分組的沒有。
  const series = first.series
  // 第一批與否照後端給的理由（`first_batch`），不在這裡再算一次。
  const firstBatch = first.reason.code === 'first_batch'
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
        firstBatch
          ? series?.ask
            ? firstBatchAskText(t, { title, group: series.group, ask: series.ask })
            : t('review.audit.series.firstBatch', { count })
          : lead.kind === 'same'
            ? t('review.audit.group.same', { count, lead: leadText(t, lead.reason) })
            : t(`review.audit.group.${lead.kind}`, { count })
      }
      when={t('review.audit.importedAt', { value: whenText(oldest, i18n.language) })}
      refusal={failed}
      details={
        series !== null ? (
          // 一個 Series 的集數多半各是一筆下載：下載那一格在每個成員自己的展開裡。
          <>
            <DetailLine term={t('review.audit.series.name')}>{series.name}</DetailLine>
            <DetailLine term={t('review.audit.series.values')}>
              {seriesValuesText(t, series) ?? t('review.audit.series.unset')}
            </DetailLine>
          </>
        ) : (
          <DetailLine term={t('review.audit.job')}>
            <JobLink hash={first.job_hash}>{first.job_name || first.job_hash}</JobLink>
          </DetailLine>
        )
      }
      members={
        <ul className="mt-2 grid gap-2">
          {rows.map((row) => (
            <li key={row.ref} className="min-w-0">
              <AuditRow
                row={row}
                onDone={onDone}
                member={{ quiet: firstBatch || lead.kind !== 'mixed' }}
              />
            </li>
          ))}
        </ul>
      }
    >
      <GhostButton type="button" busy={pending} onClick={() => confirm(rows)}>
        {pending
          ? t('review.audit.working')
          : firstBatch
            ? t('review.audit.confirmSeries')
            : t('review.audit.confirmAll')}
      </GhostButton>
    </QueueRow>
  )
}
