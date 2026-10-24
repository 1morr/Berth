import { useId } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { SubmittedJob } from '../api/assistant'
import { meQueryOptions } from '../api/auth'
import { ApiError } from '../api/client'
import { deleteJob, jobQueryOptions, refusalOf } from '../api/jobs'
import { ConfirmPanel } from '../components/ConfirmPanel'
import { CONFIRM_ACTIONS, GhostButton, PrimaryButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { SIGNAL_FILL } from '../components/signal'
import { useInPlaceConfirm } from '../components/useInPlaceConfirm'
import { JobFacts } from '../jobs/JobFacts'
import { JobLink } from '../jobs/JobLink'
import { JOB_SIGNAL, mediaTitleOf } from '../jobs/jobState'
import { CardFrame } from './cardParts'

/**
 * 送單的結果卡（M5 票 12）：送出去的那一筆 Job **現在**的樣子。
 *
 * - **即時更新**：讀 `['jobs', hash]`，側面板有這種卡時掛著 `/events/stream`（`AssistantPanel` 的 `JobStream`），
 *   poller 推播到這一筆就重問一次——與下載列表、Job 頁同一條路。存下的結果只有身分，狀態不從它畫。
 * - **撤銷走送單的反向命令**（`deletion.delete_job`）：移除 torrent、刪下載下來的檔、清紀錄，同一筆之後還送得出去。
 *   只在還沒下載完時（`undoable`，後端算）給，只有管理員按得到（刪除是 admin 的事，plan §6）；就地確認，說清楚會刪什麼。
 * - 這一筆不在了（撤銷了、或在 Job 頁刪了紀錄）說一句，不當成錯誤。
 */
export function SubmittedJobCard({ result }: { result: SubmittedJob }) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const job = useQuery(jobQueryOptions(result.hash))
  const me = useQuery(meQueryOptions)
  const gone = job.error instanceof ApiError && job.error.status === 404

  return (
    <CardFrame
      labelId={id}
      heading={t('assistant.cards.submitted.title')}
      count={result.created ? t('submit.done') : t('submit.already')}
    >
      <div className="grid gap-2 px-3 py-2.5">
        {gone ? (
          <>
            <p className="value text-sm wrap-anywhere text-ink">{result.name}</p>
            <p className="text-xs text-ink-dim">{t('assistant.cards.submitted.gone')}</p>
          </>
        ) : job.data ? (
          <>
            <p className="flex flex-wrap items-start gap-x-3 gap-y-2">
              <span
                className={`label shrink-0 px-2 py-1.5 ${SIGNAL_FILL[JOB_SIGNAL[job.data.state]]}`}
              >
                {t(`jobs.state.${job.data.state}`)}
              </span>
              <span className="value min-w-0 basis-full text-sm wrap-anywhere text-ink sm:basis-0 sm:flex-1">
                {job.data.name}
              </span>
            </p>
            <JobFacts job={job.data} media={mediaTitleOf(job.data, i18n.language)} />
            <p className="text-xs">
              <JobLink hash={result.hash}>{t('assistant.cards.submitted.open')}</JobLink>
            </p>
            {me.data?.role === 'admin' && job.data.undoable && <Undo hash={result.hash} />}
          </>
        ) : job.isError ? (
          <RequestFailed error={job.error} lead={t('assistant.cards.submitted.readFailed')} />
        ) : (
          <p className="value text-sm wrap-anywhere text-ink">{result.name}</p>
        )}
      </div>
    </CardFrame>
  )
}

/** 撤銷這次送單：DELETE 的四個旗標固定成「移除 torrent、刪檔、清紀錄」（媒體庫裡還沒有它，不必拆鏈接）。 */
function Undo({ hash }: { hash: string }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const titleId = useId()
  const undo = useMutation({
    mutationFn: () =>
      deleteJob(hash, { unlink: false, removeTorrent: true, deleteFiles: true, purge: true }),
    onSuccess: async () => {
      close()
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
        // 那幾集回到「缺」，作品頁的季表跟著換。
        queryClient.invalidateQueries({ queryKey: ['media'] }),
      ])
    },
  })
  const refusal = refusalOf(undo.error)

  if (!asked) {
    return (
      <div>
        <GhostButton ref={trigger} type="button" onClick={open}>
          {t('assistant.cards.submitted.undo')}
        </GhostButton>
      </div>
    )
  }

  return (
    <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={titleId}>
      <p id={titleId} className="max-w-prose text-xs text-ink">
        {t('assistant.cards.submitted.undoConfirm')}
      </p>
      <div className={CONFIRM_ACTIONS}>
        <PrimaryButton type="button" busy={undo.isPending} onClick={() => undo.mutate()}>
          {undo.isPending
            ? t('assistant.cards.submitted.undoing')
            : t('assistant.cards.submitted.undo')}
        </PrimaryButton>
        <GhostButton type="button" onClick={close}>
          {t('common.cancel')}
        </GhostButton>
      </div>
      {undo.isError &&
        (refusal ? (
          <p role="alert" className="max-w-prose text-xs text-blocked-ink">
            {t(`jobs.refusal.${refusal.reason}`)}
          </p>
        ) : (
          <RequestFailed error={undo.error} lead={t('assistant.cards.submitted.undoFailed')} />
        ))}
    </ConfirmPanel>
  )
}
