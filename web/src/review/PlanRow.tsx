import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { approvePlan, planQueryOptions, rejectPlan } from '../api/plans'
import { reviewQueryOptions, type PlanDecision, type PlanReviewRow } from '../api/review'
import { ConfirmAction, PrimaryButton } from '../components/controls'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { JobLink } from '../jobs/JobLink'
import { whenText } from '../components/queueText'
import { tmdbText } from '../i18n/tmdbText'
import { PlanEditor } from '../plans/PlanEditor'
import { planRefusalText } from '../plans/planRefusal'

/**
 * 一份停在 review 的 Plan（M2 票 07、`.scratch/m2/plan-edit-shape.md`）。
 *
 * **表格就地展開，不換頁**（使用者拍板）：審核在手機上要做得完（plan §7）。逐列的內容由
 * `GET /plans/{id}` 另外要——佇列那一支只帶摘要。
 *
 * 兩顆按鈕：
 *
 * - **核准並入庫**是主要動作，不另外確認：每一列會落在哪裡已經在表上了（原則 2 的「先給看」）。
 *   **批次核准與改過之後的核准是同一顆**，打的是同一支 `approve`。
 * - **拒絕**就地確認：它丟掉這份計劃連同改過的列、讓 Berth 重新規劃（plan §3.1）。
 */
export function PlanRow({ row, onDone }: { row: PlanReviewRow; onDone: (said: string) => void }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const plan = useQuery(planQueryOptions(row.job_hash, row.ref))
  const [refusal, setRefusal] = useState<string | null>(null)

  const decide = useMutation({
    mutationFn: async (decision: PlanDecision) => {
      // 核准回的那一份用不到：它一核准就離開佇列了，畫面要的是重問。
      await (decision === 'approve' ? approvePlan(row.ref) : rejectPlan(row.ref))
    },
    onMutate: () => setRefusal(null),
    onSuccess: (_, decision) => {
      onDone(decision === 'approve' ? t('review.plan.approved') : t('review.plan.rejected'))
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
      // 那一筆的狀態變了（入庫中 / 重新規劃），下載列表與它的計劃都要重問。
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (error) => {
      setRefusal(planRefusalText(t, error))
      // 另一個分頁先決定了：重問一次，那一列自己消失。擋住核准的那兩種（沒決定、撞路徑）留著讓人改。
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
    },
  })

  const busy = decide.isPending
  const title = tmdbText(i18n.language, { 'zh-Hant': row.title, en: row.title_en })

  return (
    <QueueRow
      label={t('review.plan.label')}
      heading="h3"
      // 作品名跟著 UI 語言走（brief §7.5）；沒有作品時退回發佈名，它仍然是使用者認得出的東西。
      title={title || row.job_name}
      sentence={t(`review.plan.reason.${row.reason.code}`)}
      when={t('review.plan.waitingSince', { value: whenText(row.at) })}
      refusal={refusal}
      body={
        plan.isPending ? (
          // 靜態佔位，沒有動畫（同 `/issues` 的 `Loading()`）；高度接近兩列，避免資料回來時整頁往下推。
          <div aria-hidden="true" className="h-28 border-2 border-rule bg-hull" />
        ) : plan.data ? (
          <PlanEditor plan={plan.data} hash={row.job_hash} />
        ) : (
          <p className="text-xs text-ink-dim">{t('review.plan.off')}</p>
        )
      }
      details={
        <>
          <DetailLine term={t('review.plan.job')}>
            <JobLink hash={row.job_hash}>{row.job_name}</JobLink>
          </DetailLine>
          <DetailLine term={t('jobs.plan.title')}>
            {[
              t('jobs.plan.planned', { count: row.summary.files ?? 0 }),
              t('jobs.plan.levels', {
                high: row.summary.high ?? 0,
                medium: row.summary.medium ?? 0,
                low: row.summary.low ?? 0,
              }),
            ].join(' · ')}
          </DetailLine>
        </>
      }
    >
      {row.actions.map((action) =>
        action === 'approve' ? (
          // 主要動作在窄版滿版、桌機固定寬（同 `CONFIRM_ACTIONS` 的 14rem）。
          <div key={action} className="w-full sm:w-56">
            <PrimaryButton type="button" disabled={busy} onClick={() => decide.mutate(action)}>
              {busy ? t('review.plan.working') : t('review.plan.approve')}
            </PrimaryButton>
          </div>
        ) : (
          <ConfirmAction
            key={action}
            label={t('review.plan.reject')}
            confirmLabel={t('review.plan.confirmRejectAction')}
            warning={t('review.plan.confirmReject')}
            pending={busy}
            pendingLabel={t('review.plan.working')}
            onConfirm={() => decide.mutate(action)}
          />
        ),
      )}
    </QueueRow>
  )
}
