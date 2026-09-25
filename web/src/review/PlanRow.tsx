import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { approvePlan, planQueryOptions, rejectPlan } from '../api/plans'
import { reviewQueryOptions, type PlanDecision, type PlanReviewRow } from '../api/review'
import { ConfirmAction, PrimaryButton } from '../components/controls'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { JobLink } from '../jobs/JobLink'
import { whenText } from '../components/queueText'
import { displayRound } from '../i18n/displayRound'
import { PlanEditor, type Unapplied } from '../plans/PlanEditor'
import { planRefusalText } from '../plans/planRefusal'
import type { Said } from './useConfirmAudits'

/**
 * 一份停在 review 的 Plan（M2 票 07、`.scratch/m2/plan-edit-shape.md`）。
 *
 * **表格就地展開，不換頁**（使用者拍板）：審核在手機上要做得完（plan §7）。逐列的內容由
 * `GET /plans/{id}` 另外要——佇列那一支只帶摘要。
 *
 * 兩顆按鈕：
 *
 * - **核准並入庫**是主要動作，不另外確認：每一列會落在哪裡已經在表上了（原則 2 的「先給看」）。
 *   **批次核准與改過之後的核准是同一顆**，打的是同一支 `approve`。還有列改了沒套用時不送出、說出是哪幾列
 *   （M3 票 06）：`approve` 核准的是已經存下來的那一份，表單上的值不會跟著去。
 * - **拒絕**就地確認：它丟掉這份計劃連同改過的列、讓 Berth 重新規劃（plan §3.1）。
 */
export function PlanRow({ row, onDone }: { row: PlanReviewRow; onDone: Said }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const plan = useQuery(planQueryOptions(row.job_hash, row.ref))
  const [refusal, setRefusal] = useState<string | null>(null)
  // 表單改了還沒套用的那幾列（id → 檔名），與「核准被它們擋下來了」。擋下來那一句在它們都收起之後自己消失。
  const [unapplied, setUnapplied] = useState<ReadonlyMap<number, string>>(new Map())
  const [held, setHeld] = useState(false)
  const markUnapplied = useCallback<Unapplied>((item, dirty) => {
    setUnapplied((was) => {
      if (was.has(item.id) === dirty) return was
      const next = new Map(was)
      if (dirty) next.set(item.id, item.rel_path)
      else next.delete(item.id)
      return next
    })
  }, [])

  const decide = useMutation({
    mutationFn: async (decision: PlanDecision) => {
      // 核准回的那一份用不到：它一核准就離開佇列了，畫面要的是重問。
      await (decision === 'approve' ? approvePlan(row.ref) : rejectPlan(row.ref))
    },
    onMutate: () => {
      setRefusal(null)
      setHeld(false)
    },
    onSuccess: (_, decision) => {
      onDone(decision === 'approve' ? t('review.plan.approved') : t('review.plan.rejected'))
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
      // 那一筆的狀態變了（入庫中 / 重新規劃），下載列表與它的計劃都要重問。
      void queryClient.invalidateQueries({ queryKey: ['jobs'] })
      // Media 詳情的入庫狀態也變了；那一份 5 分鐘內不重抓（`api/media.ts`），不讓它失效就停在核准之前（M3 票 06）。
      void queryClient.invalidateQueries({ queryKey: ['media'] })
    },
    onError: (error) => {
      setRefusal(planRefusalText(t, error))
      // 另一個分頁先決定了：重問一次，那一列自己消失。擋住核准的那兩種（沒決定、撞路徑）留著讓人改。
      void queryClient.invalidateQueries({ queryKey: reviewQueryOptions().queryKey })
    },
  })

  const busy = decide.isPending
  const edits = [...unapplied.values()]
  const said =
    held && edits.length > 0
      ? t('review.plan.unapplied', {
          apply: t('review.plan.apply'),
          cancel: t('review.plan.cancel'),
          files: new Intl.ListFormat(i18n.language).format(edits),
        })
      : refusal

  function approve() {
    if (edits.length === 0) return decide.mutate('approve')
    setRefusal(null)
    setHeld(true)
  }
  const title = displayRound(i18n.language, { 'zh-Hant': row.title, en: row.title_en })

  return (
    <QueueRow
      label={t('review.plan.label')}
      heading="h3"
      // 作品名跟著 UI 語言走（brief §7.5）；沒有作品時退回發佈名，它仍然是使用者認得出的東西。
      title={title || row.job_name}
      sentence={t(`review.plan.reason.${row.reason.code}`)}
      when={t('review.plan.waitingSince', { value: whenText(row.at, i18n.language) })}
      refusal={said}
      body={
        plan.isPending ? (
          // 靜態佔位，沒有動畫（同 `/issues` 的 `Loading()`）；高度接近兩列，避免資料回來時整頁往下推。
          <div aria-hidden="true" className="h-28 border-2 border-rule bg-hull" />
        ) : plan.data ? (
          <PlanEditor
            plan={plan.data}
            hash={row.job_hash}
            onUnapplied={markUnapplied}
            onSeries={(said) => onDone(said, true)}
          />
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
            <PrimaryButton type="button" busy={busy} onClick={approve}>
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
