import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useJobStream } from '../api/events'
import { jobsQueryOptions } from '../api/jobs'
import { GHOST_LINK, PAGE_TITLE } from '../components/controls'
import { JobRow } from '../jobs/JobRow'

/**
 * 下載列表頁 `/jobs`（`.scratch/m1/jobs-shape.md`，票 09）。
 *
 * 使用者在兩個時刻打開它：剛按完送單想確認真的進去了，以及「怎麼那部片還沒出現在
 * Jellyfin」。兩個時刻要的都是**逐筆的狀態與理由**——所以這一頁沒有統計數字、沒有圖表，
 * 只有一份船期表。
 *
 * **這一頁自己會動**（票 10）：`qbit_poller` 每動一筆就往 SSE 丟一個提示，這裡收到就讓
 * `['jobs']` 失效再問一次。沒有「即時」指示器、沒有脈動點——DESIGN.md 的這塊板沒有動畫，
 * 而值自己換就是訊號本身（`.scratch/m1/live-jobs-shape.md` §3，使用者拍板）。
 * 斷線由瀏覽器的 `EventSource` 自己重連，重連那一次的重問會把中間錯過的全部補上。
 *
 * 排序純粹最新在前（使用者 2026-09-10 拍板）：把失敗置頂的話，同一筆 Job 會在重試成功
 * 之後跳位置——而使用者剛剛才在那個位置按過按鈕。
 */
export function JobsPage() {
  const { t } = useTranslation()
  const jobs = useQuery(jobsQueryOptions())
  // 掛在這一頁而不是 AppShell：探索頁與設定頁不在乎 job 動了沒，而一條永遠開著的連線
  // 在後端就是一個永遠開著的訂閱。
  useJobStream()

  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-4 px-6 py-8">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h1 className={PAGE_TITLE}>{t('jobs.title')}</h1>
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
