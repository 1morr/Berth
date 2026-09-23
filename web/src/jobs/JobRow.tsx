import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import { jobEventsQueryOptions, type Job } from '../api/jobs'
import { CopyLine, GHOST_LINK } from '../components/controls'
import { AuditChip } from '../components/AuditChip'
import { ExpandHint } from '../components/ExpandHint'
import { SIGNAL_FILL } from '../components/signal'
import { JobFacts } from './JobFacts'
import { JOB_SIGNAL, mediaTitleOf } from './jobState'
import { JobTimeline } from './JobTimeline'

/** 展開區的時間線摘要畫幾段。三段夠說出「剛剛發生了什麼」，完整的一份在詳情頁。 */
const LATEST_RUNS = 3

/**
 * 船期表上的一列（`.scratch/m1/jobs-shape.md` §6）。
 *
 * **展開的是同一列，不是另一頁**（The Failure Expands In Place Rule）：`<details>` 就地展開，
 * 其他列不動。原生 `<details>` 而不是自己寫一個摺疊——全域焦點環已經涵蓋 `summary`，而原生的
 * 鍵盤行為不必重寫一次。
 *
 * **展開區只剩狀態與時間線摘要**（M2 票 12、`.scratch/m2/job-detail-shape.md`）：計劃、Plan 歷史與
 * 每一顆動作都在 `/jobs/:hash`。兩個地方各畫一份計劃的話，下一輪就會各長各的；刪除這種要二次確認
 * 的動作塞在列表裡，也說不清楚「哪一筆正在被刪」。
 *
 * 時間線**展開時才問**（`enabled`）：一份清單裡多數列不會被展開。
 */
export function JobRow({ job }: { job: Job }) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)

  const me = useQuery(meQueryOptions)
  const events = useQuery(jobEventsQueryOptions(job.hash, open))

  const mediaTitle = mediaTitleOf(job, i18n.language)
  const failed = JOB_SIGNAL[job.state] === 'blocked'

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
            <JobFacts job={job} media={mediaTitle} />
            {/* `user` 按不了審核（plan §6、brief §11），停在這裡的那一筆他只能等——說出來，
                否則黃色的「待審核」讀起來像是在叫他做什麼。 */}
            {job.state === 'review' && me.data && me.data.role !== 'admin' && (
              <span className="text-xs text-ink-dim">{t('jobs.waitingForAdmin')}</span>
            )}
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

        {events.isPending ? (
          <p className="text-xs text-ink-dim">{t('jobs.timeline.loading')}</p>
        ) : events.data ? (
          <JobTimeline events={events.data} latest={LATEST_RUNS} />
        ) : (
          <p className="text-xs text-ink-dim">{t('jobs.timeline.off')}</p>
        )}

        <div className="grid min-w-0 gap-1">
          {/* 整串 hash 是使用者拿去 qBittorrent 介面上比對的那一個。 */}
          <p className="label text-ink-dim">{t('jobs.hash')}</p>
          <CopyLine command={job.hash} />
        </div>

        {/* 計劃、完整時間線與每一顆動作都在那一頁。 */}
        <Link to="/jobs/$hash" params={{ hash: job.hash }} className={GHOST_LINK}>
          {t('jobs.detail.open')}
        </Link>
      </div>
    </details>
  )
}
