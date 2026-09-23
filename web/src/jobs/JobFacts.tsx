import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import type { Job } from '../api/jobs'
import { Dot } from '../components/Dot'
import { Timestamp } from '../components/Timestamp'
import { formatSize } from '../media/searchResult'
import { formatProgress, shortHash } from './jobState'

/**
 * 一筆 Job 的實測值那一行：作品 · Route · trigger · 大小 · 進度 · 時間 · hash。
 *
 * **一份 DOM 兩種版面**（同票 08 的結果表）：中點分隔並允許換行，窄版自己疊起來，不橫向捲動。
 * 下載列表的一列與詳情頁的身分帶畫的是同一行（M2 票 12）；作品那一格由呼叫端給——列上是字
 * （`summary` 裡不放互動元素），詳情頁是連結。
 */
export function JobFacts({ job, media }: { job: Job; media: ReactNode }) {
  const { t, i18n } = useTranslation()

  return (
    <span className="value flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-dim">
      <span>{media || '—'}</span>
      <Dot />
      <span>{job.route_name || '—'}</span>
      <Dot />
      {/* trigger 是分類不是狀態，所以中性色塊。 */}
      <span className="label bg-deck px-1.5 py-0.5 text-ink">
        {t(`jobs.trigger.${job.trigger}`)}
      </span>
      <Dot />
      {/* **每一格都自己說出它是什麼**：這一行沒有欄頭，而大小與進度在票 10 之前都是
          `—`——不帶標籤的話那兩條破折號說不出自己少了什麼（票 08 窄版做種欄的同一條）。 */}
      <span>{t('jobs.sizeInline', { value: formatSize(job.total_size, i18n.language) })}</span>
      <Dot />
      <span>{t('jobs.progressInline', { value: formatProgress(job, i18n.language) })}</span>
      <Dot />
      <Timestamp at={job.added_at} />
      <Dot />
      <span title={job.hash} className="text-ink-dim">
        {shortHash(job.hash)}
      </span>
    </span>
  )
}
