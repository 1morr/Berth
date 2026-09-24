import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  confirmAudit,
  parseReviewRefusal,
  reviewQueryOptions,
  undoAudit,
  type AuditAction,
  type AuditReviewRow,
  type AuditUndone,
} from '../api/review'
import { ConfirmAction, GhostButton } from '../components/controls'
import { formatEpisode } from '../components/episodes'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { JobLink } from '../jobs/JobLink'
import { fileName, whenText } from '../components/queueText'
import { displayRound } from '../i18n/displayRound'
import { Reasons } from '../plans/Reasons'
import { leadReason, leadText } from './leadReason'

/**
 * 一個 medium 自動入庫、等人看一眼的檔案（CONTEXT.md 的 Audit、`.scratch/m2/review-shape.md`）。
 *
 * **它已經在媒體庫裡了**，這一列問的是「對不對」。兩顆按鈕：
 *
 * - **確認**不確認：它只清一個旗標，檔案不動。
 * - **撤銷**就地確認（使用者 2026-09-23 拍板）：Jellyfin 下次掃描就少一集，而那一筆下載回到
 *   待審核——PRODUCT 原則 2 說的破壞性動作。那一句後果要說出「complete 裡的檔案不動」，
 *   否則使用者會以為撤銷等於刪掉下載。
 *
 * **收起時說出主要原因**（M3 票 05）：「信心 medium：季號是推論的（TMDB 只有一季）」，挑哪一條見
 * `leadReason`；完整理由仍在展開裡。沒有降級理由時照舊說「信心 medium，已自動入庫」。
 *
 * 在一組（同一個 Job，`AuditGroup`）裡時是組的成員（`member`）：標題只剩季集或檔名，組已經說過的
 * 那一句不再說（`quiet`）。
 *
 * 成功之後那一列從佇列上消失（重問佇列），所以結果要給看不見畫面的人另外說一次（`onDone`）。
 */
export function AuditRow({
  row,
  onDone,
  member,
}: {
  row: AuditReviewRow
  onDone: (said: string) => void
  member?: { quiet: boolean }
}) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [refusal, setRefusal] = useState<string | null>(null)

  const act = useMutation({
    mutationFn: async (action: AuditAction): Promise<AuditUndone | null> => {
      if (action === 'undo') return undoAudit(row.ref)
      await confirmAudit(row.ref)
      return null
    },
    onMutate: () => setRefusal(null),
    onSuccess: (undone, action) => {
      // 媒體庫裡那個檔案已經不是 Berth 放的那一個時沒有刪它（M3 票 01），結果那一句要說出來。
      onDone(
        action === 'confirm'
          ? t('review.audit.confirmed')
          : undone?.unmanaged
            ? t('review.audit.undoneUnmanaged')
            : t('review.audit.undone'),
      )
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
      // 撤銷把那一筆送回待審核：下載列表那一列的狀態與「N 個待確認」都變了。
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (error) => {
      const said = parseReviewRefusal(error)
      setRefusal(
        said
          ? [t(`review.audit.refusal.${said.reason}`), said.detail].filter(Boolean).join(' ')
          : t('review.audit.failed'),
      )
      // 另一個分頁先按了：重問一次，那一列自己消失。
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
    },
  })

  const busy = act.isPending
  const title = displayRound(i18n.language, { 'zh-Hant': row.title, en: row.title_en })
  const episode = formatEpisode(row)
  const lead = leadReason(row.reasons)

  return (
    <QueueRow
      label={t('review.audit.label')}
      heading={member ? 'h4' : 'h3'}
      // 作品名跟著 UI 語言走（brief §7.5）；沒有作品時退回檔名，它仍然是使用者認得出的東西。
      // 組裡的成員不再說作品名：組的標題說過了。
      title={
        member
          ? episode || fileName(row.path)
          : title
            ? [title, episode].filter(Boolean).join(' ')
            : fileName(row.path)
      }
      sentence={
        member?.quiet
          ? undefined
          : lead
            ? t('review.audit.because', { lead: leadText(t, lead) })
            : t(`review.audit.reason.${row.reason.code}`)
      }
      when={t('review.audit.importedAt', { value: whenText(row.at, i18n.language) })}
      refusal={refusal}
      details={
        <>
          <DetailLine term={t('review.audit.target')}>{row.path}</DetailLine>
          <DetailLine term={t('review.audit.source')}>{row.source_path}</DetailLine>
          {row.job_name !== '' && (
            <DetailLine term={t('review.audit.job')}>
              <JobLink hash={row.job_hash}>{row.job_name}</JobLink>
            </DetailLine>
          )}
          {row.reasons.length > 0 && (
            <DetailLine term={t('review.audit.reasons')}>
              {/* 判斷對不對的證據：為什麼是 medium。code + 參數，句子在前端（M2 票 07）。 */}
              <Reasons reasons={row.reasons} />
            </DetailLine>
          )}
        </>
      }
    >
      {row.actions.map((action) =>
        action === 'undo' ? (
          <ConfirmAction
            key={action}
            label={t('review.audit.action.undo')}
            confirmLabel={t('review.audit.confirmUndoAction')}
            warning={t('review.audit.confirmUndo')}
            pending={busy}
            pendingLabel={t('review.audit.working')}
            onConfirm={() => act.mutate(action)}
          />
        ) : (
          <GhostButton
            key={action}
            type="button"
            disabled={busy}
            onClick={() => act.mutate(action)}
          >
            {busy ? t('review.audit.working') : t(`review.audit.action.${action}`)}
          </GhostButton>
        ),
      )}
    </QueueRow>
  )
}
