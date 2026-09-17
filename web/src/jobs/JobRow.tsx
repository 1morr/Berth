import { useState } from 'react'
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
} from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { jobEventsQueryOptions, retryJob, refusalOf, type Job } from '../api/jobs'
import { planQueryOptions, replanJob } from '../api/plans'
import { CopyLine, GhostButton } from '../components/controls'
import { AuditChip } from '../components/AuditChip'
import { Dot } from '../components/Dot'
import { ExpandHint } from '../components/ExpandHint'
import { SIGNAL_FILL } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import { tmdbText } from '../i18n/tmdbText'
import { formatSize } from '../media/searchResult'
import { JOB_SIGNAL, formatProgress, shortHash } from './jobState'
import { JobPlan } from './JobPlan'
import { JobTimeline } from './JobTimeline'

/**
 * 船期表上的一列（`.scratch/m1/jobs-shape.md` §6）。
 *
 * **展開的是同一列，不是另一頁**（The Failure Expands In Place Rule）：`<details>` 就地
 * 展開時間線、hash 與重試，其他列不動、不跳頁、不開 dialog。原生 `<details>` 而不是
 * 自己寫一個摺疊——全域焦點環已經涵蓋 `summary`，而原生的鍵盤行為不必重寫一次。
 *
 * 時間線與計劃**展開時才問**（`enabled`）：一份清單裡多數列不會被展開，而每一列兩個請求會讓
 * 一頁四十筆變成八十次往返。
 *
 * 展開區的順序是**接下來 → 發生過**：計劃說的是「這幾個檔案會被寫到哪裡」，時間線說的是
 * 「它怎麼走到這裡」。使用者展開一列多半是為了前者（票 11）。
 */
export function JobRow({ job }: { job: Job }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)

  const events = useQuery(jobEventsQueryOptions(job.hash, open))
  const plan = useQuery(planQueryOptions(job.hash, job.plan_id, open))
  const retry = useMutation({
    mutationFn: () => retryJob(job.hash),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
  const replan = useMutation({
    mutationFn: () => replanJob(job.hash),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['jobs'] })
    },
  })

  // 作品名跟著 UI 語言走（brief §7.5）。沒有作品名時退回 id，摘要列與連結說的是同一個字。
  const mediaTitle =
    tmdbText(i18n.language, { 'zh-Hant': job.media_title, en: job.media_title_en }) || job.media_id
  const failed = JOB_SIGNAL[job.state] === 'blocked'
  // 同一個端點、兩種重試（plan §3.1）：送單失敗是「再送一次」，入庫失敗是「從沒鏈接的那幾個
  // 接著做」。按鈕上的字要說得出是哪一種，按下去之前才知道會發生什麼。
  const importRetry = job.state === 'import_failed'

  return (
    <details
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      // 失敗那一列**線變重**，不是變紅：紅色留給狀態色塊那一格（The One Meaning Rule）。
      className={`group min-w-0 border-2 bg-well ${failed ? 'border-rule-strong' : 'border-rule'}`}
    >
      <summary className="cursor-pointer list-none px-4 py-3">
        <span className="flex flex-wrap items-start gap-x-3 gap-y-2">
          <span className={`label shrink-0 px-2 py-1.5 ${SIGNAL_FILL[JOB_SIGNAL[job.state]]}`}>
            {t(`jobs.state.${job.state}`)}
          </span>
          <AuditChip count={job.audits} />
          {/* 窄版上它跟色塊同一行、靠右；寬版上排到最後（`sm:order-last`）。 */}
          <ExpandHint className="ml-auto sm:order-last" />
          {/* 窄版上發佈名自己一行：與兩塊色塊擠在同一行時，`wrap-anywhere` 讓它縮得下去，
              結果是一條幾個字寬的直欄（票 15 在 390px 實跑看到）。 */}
          <span className="grid min-w-0 basis-full gap-1.5 sm:basis-0 sm:flex-1">
            {/* 發佈名整行換行，不截斷：它是使用者認得出這一列的東西（票 08 §8 的同一條）。
                `wrap-anywhere` 而不是 `break-words`：沒有空格的發佈名在後者底下仍然是 flex
                子項的最小寬度，390px 上整頁橫向捲動（票 15 實測）。 */}
            <span className="value block text-sm wrap-anywhere text-ink">{job.name}</span>
            <Facts job={job} mediaTitle={mediaTitle} locale={i18n.language} />
          </span>
        </span>
      </summary>

      <div className="grid gap-3 border-t-2 border-rule bg-hull px-4 py-3 [&>*]:min-w-0">
        {/* 作品連結在這裡而不是摘要列：`<summary>` 本身是一顆按鈕，按鈕裡不能再包連結。 */}
        {open && job.media_id && (
          <p className="flex flex-wrap items-baseline gap-x-2">
            <span className="label text-ink-dim">{t('jobs.media')}</span>
            <Link
              to="/media/$mediaId"
              params={{ mediaId: job.media_id }}
              className="value text-xs text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
            >
              {mediaTitle}
            </Link>
          </p>
        )}

        {/* **先問有沒有 `plan_id`**：停用的 query 在 TanStack 眼裡永遠是 `pending`，
            所以順序反過來的話還沒算過計劃的那幾列會永遠掛著一句「讀取計劃…」。 */}
        {job.plan_id === null ? null : plan.isPending ? (
          <p className="text-xs text-ink-dim">{t('jobs.plan.loading')}</p>
        ) : plan.data ? (
          <JobPlan plan={plan.data} />
        ) : (
          <p className="text-xs text-ink-dim">{t('jobs.plan.off')}</p>
        )}

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

        {job.replannable && (
          <Action
            run={replan}
            idle={t('jobs.plan.replan')}
            busy={t('jobs.plan.replanning')}
            off={t('jobs.plan.replanOff')}
          />
        )}

        {job.retryable && (
          <Action
            run={retry}
            idle={importRetry ? t('jobs.retryImport') : t('jobs.retry')}
            busy={importRetry ? t('jobs.retryingImport') : t('jobs.retrying')}
            off={t('jobs.retryOff')}
          />
        )}
        {/* 重試成功時畫面上動的只有這一小塊，看不見畫面的人得知道發生了什麼。 */}
        <p aria-live="polite" className="sr-only">
          {retry.isSuccess ? t('jobs.retried', { state: t(`jobs.state.${job.state}`) }) : ''}
          {replan.isSuccess
            ? t('jobs.plan.replanned', { state: t(`jobs.state.${job.state}`) })
            : ''}
        </p>
      </div>
    </details>
  )
}

/**
 * 展開區裡的一顆次要動作按鈕，加上它失敗時那一句話。
 *
 * 重試與重新規劃的形狀一模一樣，所以它們是同一個元件：**按鈕永遠按得下去，只換文字**
 * （票 02b），失敗時說的是那個封閉集合的理由而不是一句通用的話（PRODUCT 原則 4），
 * 認不得的理由才落回 `off`。
 *
 * `justify-items-start`：次要動作不佔滿整條展開區——滿版是主要動作的形狀
 * （`PrimaryButton`），而這兩顆都會真的再打一次外部服務。
 */
function Action({
  run,
  idle,
  busy,
  off,
}: {
  run: UseMutationResult<Job, Error, void, unknown>
  idle: string
  busy: string
  off: string
}) {
  const { t } = useTranslation()
  const refusal = refusalOf(run.error)

  return (
    <div className="grid justify-items-start gap-2">
      <GhostButton type="button" onClick={() => run.mutate()}>
        {run.isPending ? busy : idle}
      </GhostButton>
      {run.isError && (
        <p role="alert" className="max-w-prose text-xs text-blocked-ink">
          {refusal ? t(`jobs.refusal.${refusal.reason}`) : off}
        </p>
      )}
    </div>
  )
}

/**
 * 列上的實測值那一行：作品 · Route · trigger · 大小 · 進度 · 時間。
 *
 * **一份 DOM 兩種版面**（同票 08 的結果表）：中點分隔並允許換行，窄版自己疊起來，
 * 不橫向捲動。作品在這裡只是字——它的連結在展開區（`summary` 裡不放互動元素）。
 */
function Facts({
  job,
  mediaTitle,
  locale,
}: {
  job: Job
  mediaTitle: string | null
  locale: string
}) {
  const { t } = useTranslation()

  return (
    <span className="value flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-dim">
      <span>{mediaTitle || '—'}</span>
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
