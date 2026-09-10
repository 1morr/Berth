import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { jobsQueryOptions } from '../api/jobs'
import { GHOST_LINK } from '../components/controls'
import { JobRow } from '../jobs/JobRow'

/**
 * 下載列表頁 `/jobs`（`.scratch/m1/jobs-shape.md`，票 09）。
 *
 * 使用者在兩個時刻打開它：剛按完送單想確認真的進去了，以及「怎麼那部片還沒出現在
 * Jellyfin」。兩個時刻要的都是**逐筆的狀態與理由**——所以這一頁沒有統計數字、沒有圖表，
 * 只有一份船期表。
 *
 * **這一票是靜態的**：重新整理才會變。真的會自己跑的進度要等票 10 的 `qbit_poller`
 * 與 SSE（plan §3.2、§6 events 群組）；在那之前每 N 秒重問一次只是替後端加負擔，
 * 而 M1 票 09 的三個狀態本來就只在使用者按下按鈕時才動。
 *
 * 排序純粹最新在前（使用者 2026-09-10 拍板）：把失敗置頂的話，同一筆 Job 會在重試成功
 * 之後跳位置——而使用者剛剛才在那個位置按過按鈕。
 */
export function JobsPage() {
  const { t } = useTranslation()
  const jobs = useQuery(jobsQueryOptions())

  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-4 px-6 py-8">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h1 className="label text-ink">{t('jobs.title')}</h1>
        {jobs.data && jobs.data.length > 0 && (
          <p className="value text-xs text-ink-dim">
            {t('jobs.count', { count: jobs.data.length })}
          </p>
        )}
      </div>

      {jobs.isPending ? (
        <Loading />
      ) : !jobs.data ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('jobs.off')}</p>
      ) : jobs.data.length === 0 ? (
        <Empty />
      ) : (
        <ul className="grid gap-3">
          {jobs.data.map((job) => (
            <li key={job.hash} className="min-w-0">
              <JobRow job={job} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * 一筆都沒有。**這不是錯誤**——它是每一個新使用者的第一眼，所以它說得出下一步
 * （PRODUCT 原則 4 的同一個道理：畫面永遠要有下一步）。
 */
function Empty() {
  const { t } = useTranslation()

  return (
    <div className="grid gap-3 border-2 border-rule bg-well px-4 py-4">
      <p className="max-w-prose text-sm text-ink">{t('jobs.empty')}</p>
      <Link to="/" className={GHOST_LINK}>
        {t('jobs.toDiscover')}
      </Link>
    </div>
  )
}

/** 讀取中：兩條不動的空列。**不會動**——這個世界沒有骨架屏動畫。 */
function Loading() {
  return (
    <div className="grid gap-3" aria-hidden="true">
      {[0, 1].map((index) => (
        <div key={index} className="grid gap-2 border-2 border-rule bg-well px-4 py-3">
          <span className="block h-4 w-3/5 bg-deck" />
          <span className="block h-3 w-2/5 bg-deck" />
        </div>
      ))}
    </div>
  )
}
