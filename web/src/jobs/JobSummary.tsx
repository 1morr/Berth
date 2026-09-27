import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { meQueryOptions } from '../api/auth'
import type { Job } from '../api/jobs'
import { AuditChip } from '../components/AuditChip'
import { ExpandHint } from '../components/ExpandHint'
import { SIGNAL_FILL } from '../components/signal'
import { JobFacts } from './JobFacts'
import { JOB_SIGNAL } from './jobState'

/**
 * 船期列 `<summary>` 裡的那一塊：狀態色塊、待確認、展開提示、發佈名、實測值那一行。
 *
 * 下載列表的一列（`JobRow`）與作品頁「下載」段的一列（`media/DownloadsPanel`）共用它：兩處的展開區不同
 * （時間線 / 檔案），摘要是同一件事。`media` 是作品那一格；作品頁不給，整頁都是那一部。
 */
export function JobSummary({ job, media }: { job: Job; media?: string }) {
  const { t } = useTranslation()
  const me = useQuery(meQueryOptions)

  return (
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
        <JobFacts job={job} media={media} />
        {/* `user` 按不了審核（plan §6、brief §11），停在這裡的那一筆他只能等——說出來，
            否則黃色的「待審核」讀起來像是在叫他做什麼。 */}
        {job.state === 'review' && me.data && me.data.role !== 'admin' && (
          <span className="text-xs text-ink-dim">{t('jobs.waitingForAdmin')}</span>
        )}
      </span>
    </span>
  )
}
