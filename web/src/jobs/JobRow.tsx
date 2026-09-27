import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { jobEventsQueryOptions, type Job } from '../api/jobs'
import { CopyLine, GHOST_LINK } from '../components/controls'
import { JobSummary } from './JobSummary'
import { jobRowFrame, mediaTitleOf } from './jobState'
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

  const events = useQuery(jobEventsQueryOptions(job.hash, open))

  const mediaTitle = mediaTitleOf(job, i18n.language)

  return (
    <details
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      className={jobRowFrame(job)}
    >
      <summary className="cursor-pointer list-none px-4 py-3">
        <JobSummary job={job} media={mediaTitle} />
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
