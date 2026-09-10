import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { jobEventsQueryOptions, retryJob, refusalOf, type Job } from '../api/jobs'
import { CopyLine, GhostButton } from '../components/controls'
import { Dot } from '../components/Dot'
import { SIGNAL_FILL } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import { formatSize } from '../media/searchResult'
import { JOB_SIGNAL, formatProgress, shortHash } from './jobState'
import { JobTimeline } from './JobTimeline'

/**
 * 船期表上的一列（`.scratch/m1/jobs-shape.md` §6）。
 *
 * **展開的是同一列，不是另一頁**（The Failure Expands In Place Rule）：`<details>` 就地
 * 展開時間線、hash 與重試，其他列不動、不跳頁、不開 dialog。原生 `<details>` 而不是
 * 自己寫一個摺疊——全域焦點環已經涵蓋 `summary`，而原生的鍵盤行為不必重寫一次。
 *
 * 時間線**展開時才問**（`enabled`）：一份清單裡多數列不會被展開，而每一列一個請求會讓
 * 一頁四十筆變成四十次往返。
 */
export function JobRow({ job }: { job: Job }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)

  const events = useQuery(jobEventsQueryOptions(job.hash, open))
  const retry = useMutation({
    mutationFn: () => retryJob(job.hash),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  const failed = JOB_SIGNAL[job.state] === 'blocked'
  const refusal = refusalOf(retry.error)

  return (
    <details
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      // 失敗那一列**線變重**，不是變紅：紅色留給狀態色塊那一格（The One Meaning Rule）。
      className={`min-w-0 border-2 bg-well ${failed ? 'border-rule-strong' : 'border-rule'}`}
    >
      <summary className="cursor-pointer list-none px-4 py-3">
        <span className="flex flex-wrap items-start gap-x-3 gap-y-2">
          <span className={`label shrink-0 px-2 py-1.5 ${SIGNAL_FILL[JOB_SIGNAL[job.state]]}`}>
            {t(`jobs.state.${job.state}`)}
          </span>
          <span className="grid min-w-0 flex-1 gap-1.5">
            {/* 發佈名整行換行，不截斷：它是使用者認得出這一列的東西（票 08 §8 的同一條）。 */}
            <span className="value block text-sm break-words text-ink">{job.name}</span>
            <Facts job={job} locale={i18n.language} />
          </span>
        </span>
      </summary>

      <div className="grid gap-3 border-t-2 border-rule bg-hull px-4 py-3 [&>*]:min-w-0">
        {events.isPending ? (
          <p className="text-xs text-ink-dim">{t('jobs.timeline.loading')}</p>
        ) : events.data ? (
          <JobTimeline events={events.data} />
        ) : (
          <p className="text-xs text-ink-dim">{t('jobs.timeline.off')}</p>
        )}

        <div className="grid min-w-0 gap-1">
          {/* 整串 hash 是使用者拿去 qBittorrent 介面上比對的那一個。 */}
          <p className="label text-ink-dim">{t('jobs.hash')}</p>
          <CopyLine command={job.hash} />
        </div>

        {job.retryable && (
          // `justify-items-start`：次要動作不佔滿整條展開區——滿版是主要動作的形狀
          // （`PrimaryButton`），而重試會真的再打一次索引站與 qBittorrent。
          <div className="grid justify-items-start gap-2">
            {/* 按鈕永遠按得下去，只換文字（票 02b）。 */}
            <GhostButton type="button" onClick={() => retry.mutate()}>
              {retry.isPending ? t('jobs.retrying') : t('jobs.retry')}
            </GhostButton>
            {retry.isError && (
              <p role="alert" className="max-w-prose text-xs text-blocked-ink">
                {refusal ? t(`jobs.refusal.${refusal.reason}`) : t('jobs.retryOff')}
              </p>
            )}
          </div>
        )}
        {/* 重試成功時畫面上動的只有這一小塊，看不見畫面的人得知道發生了什麼。 */}
        <p aria-live="polite" className="sr-only">
          {retry.isSuccess ? t('jobs.retried', { state: t(`jobs.state.${job.state}`) }) : ''}
        </p>
      </div>
    </details>
  )
}

/**
 * 列上的實測值那一行：作品 · Route · trigger · 大小 · 進度 · 時間。
 *
 * **一份 DOM 兩種版面**（同票 08 的結果表）：中點分隔並允許換行，窄版自己疊起來，
 * 不橫向捲動。作品是這一頁唯一的導航出口。
 */
function Facts({ job, locale }: { job: Job; locale: string }) {
  const { t } = useTranslation()

  return (
    <span className="value flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-dim">
      {job.media_id ? (
        <Link
          to="/media/$mediaId"
          params={{ mediaId: job.media_id }}
          onClick={(event) => event.stopPropagation()}
          className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
        >
          {job.media_title || job.media_id}
        </Link>
      ) : (
        <span>—</span>
      )}
      <Dot />
      <span>{job.route_name || '—'}</span>
      <Dot />
      {/* trigger 是分類不是狀態，所以中性色塊。 */}
      <span className="label bg-deck px-1.5 py-0.5 text-ink">
        {t(`jobs.trigger.${job.trigger}`)}
      </span>
      <Dot />
      {/* **每一格都自己說出它是什麼**：這一列沒有欄頭，而大小與進度在票 10 之前都是
          `—`——不帶標籤的話那兩條破折號說不出自己少了什麼（票 08 窄版做種欄的同一條）。 */}
      <span>{t('jobs.sizeInline', { value: formatSize(job.total_size, locale) })}</span>
      <Dot />
      <span>{t('jobs.progressInline', { value: formatProgress(job, locale) })}</span>
      <Dot />
      <Timestamp at={job.added_at} />
      <Dot />
      <span title={job.hash} className="text-ink-dim">
        {shortHash(job.hash)}
      </span>
    </span>
  )
}
