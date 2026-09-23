import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import { ApiError } from '../api/client'
import { useJobStream } from '../api/events'
import { jobEventsQueryOptions, jobQueryOptions, type Job } from '../api/jobs'
import { planQueryOptions } from '../api/plans'
import { AuditChip } from '../components/AuditChip'
import { CopyLine, GHOST_LINK, PAGE_TITLE } from '../components/controls'
import { DetailLine } from '../components/QueueRow'
import { SIGNAL_FILL } from '../components/signal'
import { JobActions } from '../jobs/JobActions'
import { planHistory } from '../jobs/eventTypes'
import { JobFacts } from '../jobs/JobFacts'
import { JobPlan } from '../jobs/JobPlan'
import { JOB_SIGNAL, mediaTitleOf } from '../jobs/jobState'
import { JobTimeline } from '../jobs/JobTimeline'

/** 連結的底線：作品名是散文裡的一個字，不是一顆按鈕。 */
const INLINE_LINK =
  'text-ink underline decoration-rule-strong underline-offset-4 hover:decoration-ink'

/**
 * Job 詳情 `/jobs/:hash`（brief §13、M2 票 12、`.scratch/m2/job-detail-shape.md`）。
 *
 * **另建一頁而不是展開區**（plan §11.3 決定 1）：刪除範圍是要二次確認的破壞性動作，確認區展開時
 * 畫面上方要是這一筆的名字，而不是清單裡擠進來的另一列。由上到下是「這是哪一筆 → 能對它做什麼 →
 * 檔案會落在哪、這份決定怎麼變成現在這樣 → 事情怎麼走到這裡」；寬版把最後兩件分成兩欄。
 *
 * 一般使用者也進得來（他看得到自己的下載，brief §11）；重新入庫與刪除只給 admin，後端同時回 403。
 */
export function JobDetailPage({ hash }: { hash: string }) {
  const { t } = useTranslation()
  const job = useQuery(jobQueryOptions(hash))
  // 背景迴圈動了這一筆就重問（`['jobs']` 整個前綴失效），與下載列表同一條連線的規矩。
  useJobStream()

  if (job.isPending) return <Loading />
  if (job.error instanceof ApiError && job.error.status === 404) return <Missing />
  if (!job.data) {
    return (
      <Page>
        <BackLink />
        <p className="max-w-prose text-sm text-ink-dim">{t('jobs.detail.off')}</p>
      </Page>
    )
  }
  return <Detail job={job.data} />
}

function Detail({ job }: { job: Job }) {
  const { t, i18n } = useTranslation()
  const me = useQuery(meQueryOptions)
  const events = useQuery(jobEventsQueryOptions(job.hash, true))
  const plan = useQuery(planQueryOptions(job.hash, job.plan_id))

  const isAdmin = me.data?.role === 'admin'
  const mediaTitle = mediaTitleOf(job, i18n.language)
  const history = events.data ? planHistory(events.data) : []

  return (
    <Page>
      <BackLink />

      <header className="grid min-w-0 gap-3 border-b-2 border-rule-strong pb-4">
        <div className="flex flex-wrap items-center gap-2">
          {/* 整頁唯一的信號色（The Usual Stays Unpainted Rule 的反面：這一格就是這一筆的狀態）。 */}
          <span className={`label px-2 py-1.5 ${SIGNAL_FILL[JOB_SIGNAL[job.state]]}`}>
            {t(`jobs.state.${job.state}`)}
          </span>
          <AuditChip count={job.audits} />
        </div>
        {/* 發佈名是這一頁的標題：它是使用者認得出這一筆的東西，整行換行不截斷。 */}
        <h1 className={`${PAGE_TITLE} wrap-anywhere`}>{job.name}</h1>
        <JobFacts
          job={job}
          media={
            job.media_id ? (
              <Link to="/media/$mediaId" params={{ mediaId: job.media_id }} className={INLINE_LINK}>
                {mediaTitle}
              </Link>
            ) : null
          }
        />
        {job.state === 'review' &&
          (isAdmin ? (
            <Link to="/review" className={GHOST_LINK}>
              {t('jobs.toReview')}
            </Link>
          ) : (
            me.data && <p className="text-xs text-ink-dim">{t('jobs.waitingForAdmin')}</p>
          ))}

        <dl className="grid gap-2">
          <DetailLine term={t('jobs.detail.sentBy')}>
            {job.user_name || t('jobs.detail.nobody')}
          </DetailLine>
          {job.error && (
            <DetailLine term={t('jobs.detail.error')}>
              {/* 服務回的原文，不翻譯（與時間線的 `submit_failed` 同一個規矩）。 */}
              <span className="text-blocked-ink">{job.error}</span>
            </DetailLine>
          )}
          <DetailLine term={t('jobs.hash')}>
            <CopyLine command={job.hash} />
          </DetailLine>
        </dl>
      </header>

      <JobActions job={job} isAdmin={isAdmin} />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <div className="grid min-w-0 content-start gap-8">
          <Section title={t('jobs.detail.files')}>
            {/* **先問有沒有 `plan_id`**：停用的 query 在 TanStack 眼裡永遠是 `pending`。 */}
            {job.plan_id === null ? (
              <p className="max-w-prose text-xs text-ink-dim">{t('jobs.detail.noPlan')}</p>
            ) : plan.isPending ? (
              <p className="text-xs text-ink-dim">{t('jobs.plan.loading')}</p>
            ) : plan.data ? (
              <JobPlan plan={plan.data} />
            ) : (
              <p className="text-xs text-ink-dim">{t('jobs.plan.off')}</p>
            )}
          </Section>

          {/* 沒有計劃就沒有它的歷史——除非時間線上真的有（被拒絕之後、下一份還沒算出來的那一刻）。 */}
          {(job.plan_id !== null || history.length > 0) && (
            <Section title={t('jobs.detail.history')}>
              {events.isPending ? (
                <p className="text-xs text-ink-dim">{t('jobs.timeline.loading')}</p>
              ) : !events.data ? (
                <p className="text-xs text-ink-dim">{t('jobs.timeline.off')}</p>
              ) : history.length === 0 ? (
                <p className="text-xs text-ink-dim">{t('jobs.detail.historyEmpty')}</p>
              ) : (
                <JobTimeline events={history} />
              )}
            </Section>
          )}
        </div>

        <Section title={t('jobs.detail.timeline')}>
          {events.isPending ? (
            <p className="text-xs text-ink-dim">{t('jobs.timeline.loading')}</p>
          ) : events.data ? (
            <JobTimeline events={events.data} />
          ) : (
            <p className="text-xs text-ink-dim">{t('jobs.timeline.off')}</p>
          )}
        </Section>
      </div>
    </Page>
  )
}

/** 決策與清單那一種頁寬（DESIGN.md 的頁寬三種）。 */
function Page({ children }: { children: ReactNode }) {
  return <div className="mx-auto grid w-full max-w-[80rem] gap-6 px-6 py-8">{children}</div>
}

function BackLink() {
  const { t } = useTranslation()
  return (
    <Link to="/jobs" className={GHOST_LINK}>
      {t('jobs.detail.back')}
    </Link>
  )
}

/** 一段：`.label` 模板字壓在重橫線上（DESIGN.md 的區塊標題），底下是內容。 */
function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="grid min-w-0 content-start gap-3">
      <h2 className="label border-b-2 border-rule-strong pb-2 text-ink">{title}</h2>
      {children}
    </section>
  )
}

/**
 * 不存在的 hash。多半是打錯了，或那一筆刪除時勾了「清除紀錄」——在這一頁上刪掉的那一刻也落在這裡，
 * 所以這一句要說得出兩種可能，並給回去的路。
 */
function Missing() {
  const { t } = useTranslation()
  return (
    <Page>
      <div className="grid gap-3 border-2 border-rule bg-well px-4 py-4">
        <h1 className={PAGE_TITLE}>{t('jobs.detail.missing')}</h1>
        <p className="max-w-prose text-sm text-ink-dim">{t('jobs.detail.missingHint')}</p>
        <BackLink />
      </div>
    </Page>
  )
}

/** 讀取中：身分帶位置兩條不動的色條。**不會動**——這個世界沒有骨架屏動畫。 */
function Loading() {
  const { t } = useTranslation()
  return (
    <Page>
      <p className="sr-only" aria-live="polite">
        {t('jobs.detail.loading')}
      </p>
      <div className="grid gap-3 border-b-2 border-rule-strong pb-4" aria-hidden="true">
        <span className="block h-6 w-24 bg-deck" />
        <span className="block h-5 w-3/5 bg-deck" />
        <span className="block h-3 w-2/5 bg-deck" />
      </div>
    </Page>
  )
}
