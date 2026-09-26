import { useQuery } from '@tanstack/react-query'
import { Link, useSearch } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import { useJobStream } from '../api/events'
import { JOB_FILTERS, jobsQueryOptions, type JobFilter, type JobPage } from '../api/jobs'
import { FILTER, FILTER_ACTIVE, GHOST_LINK, PAGE_TITLE } from '../components/controls'
import { PAGE_LINK, Pager } from '../components/Pager'
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
 *
 * **一頁 50 筆、分四組**（M4 票 04，`.scratch/m4/jobs-paging-shape.md`）：RSS 一次綁定就送上百筆，而入庫的
 * 不會離開清單。預設看「在路上」的——兩個打開它的時刻要看的都是還沒入庫的；分組不改排序。篩選與頁碼
 * 在網址上，形狀照媒體庫的牆（`?filter=&page=`、`1–50 / 523` 加上一頁 / 下一頁）。
 */
export function JobsPage() {
  const { t } = useTranslation()
  const search = useSearch({ from: '/jobs' })
  const filter: JobFilter = search.filter ?? 'active'
  const page = search.page ?? 1
  const jobs = useQuery(jobsQueryOptions(filter, page))
  // 掛在這一頁而不是 AppShell：探索頁與設定頁不在乎 job 動了沒，而一條永遠開著的連線
  // 在後端就是一個永遠開著的訂閱。
  useJobStream()

  const listing = jobs.data
  // 換篩選時手上的是上一組的那一頁（`placeholderData`）：篩選列與件數照畫，列要等這一組回來。
  const settled = listing?.filter === filter

  return (
    <div className="mx-auto grid w-full max-w-[80rem] gap-4 px-6 py-8">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h1 className={PAGE_TITLE}>{t('jobs.title')}</h1>
        {listing && listing.counts.all > 0 && (
          <p className="value text-xs text-ink-dim">
            {t('jobs.count', { count: listing.counts.all })}
          </p>
        )}
      </div>

      {jobs.isPending ? (
        <Loading />
      ) : !listing ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('jobs.off')}</p>
      ) : listing.counts.all === 0 ? (
        <Empty />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Filters listing={listing} filter={filter} />
            {settled && <JobsPager listing={listing} filter={filter} announce />}
          </div>
          {!settled ? (
            <Loading />
          ) : listing.jobs.length === 0 ? (
            <EmptyFilter listing={listing} filter={filter} />
          ) : (
            <ul className="grid gap-3">
              {listing.jobs.map((job) => (
                <li key={job.hash} className="min-w-0">
                  <JobRow job={job} />
                </li>
              ))}
            </ul>
          )}
          {/* 清單底那一組只在真的有別頁時出現：只有一頁時範圍已經寫在篩選列旁。 */}
          {settled &&
            listing.jobs.length > 0 &&
            (listing.total > listing.page_size || listing.page > 1) && (
              <div className="flex justify-end">
                <JobsPager listing={listing} filter={filter} end />
              </div>
            )}
        </>
      )}
    </div>
  )
}

/** 這一個篩選的網址參數：預設的篩選與第 1 頁不寫進網址（`routes.tsx` 的 `JobsSearch`）。 */
function onFilter(filter: JobFilter, page = 1) {
  return {
    ...(filter === 'active' ? {} : { filter }),
    ...(page > 1 ? { page } : {}),
  }
}

/**
 * 在路上 · 需要人 · 已入庫 · 全部，各帶件數（整張表的，不隨頁碼變）。換篩選回到第 1 頁：
 * 別組的第 3 頁與這一組的第 3 頁沒有關係。
 *
 * **選著的那一個不是連結**，是一段 `aria-current="true"` 的字——與媒體庫的篩選同一條（M1.5 票 13）。
 */
function Filters({ listing, filter }: { listing: JobPage; filter: JobFilter }) {
  const { t } = useTranslation()

  return (
    <nav aria-label={t('jobs.filters')} className="flex flex-wrap gap-2">
      {JOB_FILTERS.map((option) => {
        const label = t(`jobs.filter.${option}`, { count: listing.counts[option] })
        return option === filter ? (
          <span key={option} aria-current="true" className={`${FILTER_ACTIVE} text-ink`}>
            {label}
          </span>
        ) : (
          <Link key={option} to="/jobs" search={onFilter(option)} className={FILTER}>
            {label}
          </Link>
        )
      })}
    </nav>
  )
}

function JobsPager({
  listing,
  filter,
  announce = false,
  end = false,
}: {
  listing: JobPage
  filter: JobFilter
  announce?: boolean
  /** 清單底那一組。 */
  end?: boolean
}) {
  const { t } = useTranslation()
  const { page, page_size: size, total } = listing

  return (
    <Pager
      page={page}
      size={size}
      total={total}
      label={end ? t('jobs.pagesEnd') : t('jobs.pages')}
      announce={
        announce
          ? (range) =>
              range.beyond
                ? t('jobs.rangeBeyond', { total })
                : t('jobs.range', { first: range.first, last: range.last, total })
          : undefined
      }
      link={(to, children) => (
        <Link to="/jobs" search={onFilter(filter, to)} className={PAGE_LINK}>
          {children}
        </Link>
      )}
    />
  )
}

/**
 * 這一頁是空的，但整份清單不是。兩種：頁碼超過最後一頁（翻頁的當下有幾筆移到別組），給回第一頁的路；
 * 這一組本來就是空的，給去別組的路——空的是篩選的結果，不是下載列表本身（PRODUCT 原則 4）。
 */
function EmptyFilter({ listing, filter }: { listing: JobPage; filter: JobFilter }) {
  const { t } = useTranslation()
  const beyond = listing.total > 0
  // `all` 空的時候整份清單就是空的，那是 `Empty`，到不了這裡。
  const shown = filter === 'all' ? 'active' : filter
  const elsewhere = shown === 'active' ? 'imported' : 'active'

  return (
    <div className="grid justify-items-start gap-3 border-2 border-rule bg-well px-4 py-4">
      <p className="max-w-prose text-sm text-ink">
        {beyond ? t('jobs.emptyPage') : t(`jobs.emptyFilter.${shown}`)}
      </p>
      {beyond ? (
        <Link to="/jobs" search={onFilter(filter)} className={GHOST_LINK}>
          {t('jobs.toFirstPage')}
        </Link>
      ) : (
        <Link to="/jobs" search={onFilter(elsewhere)} className={GHOST_LINK}>
          {t(`jobs.toFilter.${elsewhere}`)}
        </Link>
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
