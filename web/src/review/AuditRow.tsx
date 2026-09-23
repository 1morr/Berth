import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  confirmAudit,
  parseReviewRefusal,
  reviewQueryOptions,
  undoAudit,
  type AuditAction,
  type AuditReviewRow,
} from '../api/review'
import { ConfirmAction, GhostButton } from '../components/controls'
import { formatEpisode } from '../components/episodes'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { fileName, whenText } from '../components/queueText'
import { tmdbText } from '../i18n/tmdbText'
import { Reasons } from '../plans/Reasons'

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
 * 成功之後那一列從佇列上消失（重問佇列），所以結果要給看不見畫面的人另外說一次（`onDone`）。
 */
export function AuditRow({ row, onDone }: { row: AuditReviewRow; onDone: (said: string) => void }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [refusal, setRefusal] = useState<string | null>(null)

  const act = useMutation({
    mutationFn: (action: AuditAction) =>
      action === 'confirm' ? confirmAudit(row.ref) : undoAudit(row.ref),
    onMutate: () => setRefusal(null),
    onSuccess: (_, action) => {
      onDone(action === 'confirm' ? t('review.audit.confirmed') : t('review.audit.undone'))
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
  const title = tmdbText(i18n.language, { 'zh-Hant': row.title, en: row.title_en })
  const episode = formatEpisode(row)

  return (
    <QueueRow
      label={t('review.audit.label')}
      heading="h3"
      // 作品名跟著 UI 語言走（brief §7.5）；沒有作品時退回檔名，它仍然是使用者認得出的東西。
      title={title ? [title, episode].filter(Boolean).join(' ') : fileName(row.path)}
      sentence={t(`review.audit.reason.${row.reason.code}`)}
      when={t('review.audit.importedAt', { value: whenText(row.at) })}
      refusal={refusal}
      details={
        <>
          <DetailLine term={t('review.audit.target')}>{row.path}</DetailLine>
          <DetailLine term={t('review.audit.source')}>{row.source_path}</DetailLine>
          {row.job_name !== '' && (
            <DetailLine term={t('review.audit.job')}>
              {/* 下載列表是它的家：時間線與整份計劃都在那裡。 */}
              <Link
                to="/jobs"
                className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
              >
                {row.job_name}
              </Link>
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
