import { useContext, useId } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { SubmittedJob } from '../api/assistant'
import { ApiError } from '../api/client'
import { jobQueryOptions } from '../api/jobs'
import { RequestFailed } from '../components/RequestFailed'
import { SIGNAL_FILL } from '../components/signal'
import { useFocusOnSettle } from '../components/useFocusOnSettle'
import { JobFacts } from '../jobs/JobFacts'
import { JobLink } from '../jobs/JobLink'
import { JOB_SIGNAL, mediaTitleOf } from '../jobs/jobState'
import { CardFrame } from './cardParts'
import { ToolCallContext } from './toolCall'
import { UndoButton } from './UndoButton'

/**
 * 送單的結果卡（M5 票 12）：送出去的那一筆 Job **現在**的樣子。
 *
 * - **即時更新**：讀 `['jobs', hash]`，側面板有這種卡時掛著 `/events/stream`（`AssistantPanel` 的 `JobStream`），
 *   poller 推播到這一筆就重問一次——與下載列表、Job 頁同一條路。存下的結果只有身分，狀態不從它畫。
 * - **撤銷走送單的反向命令**（`deletion.withdraw_job`）：移除 torrent、刪下載下來的檔、清紀錄，同一筆之後還送得出去。
 *   只在還沒下載完時（`JobOut.undoable`，後端算）給，按不按得到照後端說的（刪除是 admin 的事，plan §6）；就地確認，
 *   說清楚會刪什麼。撤銷經過對話（`UndoButton`，M5 票 11），模型下一輪知道。
 * - 這一筆不在了（撤銷了、或在 Job 頁刪了紀錄）說一句，不當成錯誤。
 */
export function SubmittedJobCard({ result }: { result: SubmittedJob }) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const { undone } = useContext(ToolCallContext)
  const job = useQuery({ ...jobQueryOptions(result.hash), enabled: undone === null })
  const gone = job.error instanceof ApiError && job.error.status === 404
  // 撤銷鍵消失了：焦點落在說已撤銷的那一句（M5 票 15）。
  const status = useFocusOnSettle<HTMLParagraphElement>(undone !== null)

  return (
    <CardFrame
      labelId={id}
      heading={t('assistant.cards.submitted.title')}
      count={
        undone
          ? t('assistant.cards.submitted.undoneCount')
          : result.created
            ? t('submit.done')
            : t('submit.already')
      }
    >
      <div className="grid gap-2 px-3 py-2.5">
        {undone || gone ? (
          <>
            <p className="value text-sm wrap-anywhere text-ink">{result.name}</p>
            <p
              ref={status}
              role={undone ? 'status' : undefined}
              tabIndex={undone ? -1 : undefined}
              className="text-xs text-ink-dim"
            >
              {undone ? t('assistant.cards.submitted.undone') : t('assistant.cards.submitted.gone')}
            </p>
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
            {job.data.undoable && (
              <UndoButton
                label={t('assistant.cards.submitted.undo')}
                confirm={t('assistant.cards.submitted.undoConfirm')}
                // 那幾集回到「缺」，作品頁的季表跟著換。
                invalidate={[['jobs'], ['media']]}
              />
            )}
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
