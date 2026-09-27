import { Fragment, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import type { TFunction } from 'i18next'
import { useTranslation } from 'react-i18next'

import { useJobStream } from '../api/events'
import {
  jobFilesQueryOptions,
  mediaJobsQueryOptions,
  type Job,
  type JobFile,
  type JobPage,
  type MediaJobFilter,
} from '../api/jobs'
import type { Media } from '../api/media'
import { FILTER, FILTER_ACTIVE, GHOST_LINK, GhostButton } from '../components/controls'
import { Dot } from '../components/Dot'
import { formatEpisode } from '../components/episodes'
import { Pager, PAGE_LINK } from '../components/Pager'
import { JobSummary } from '../jobs/JobSummary'
import { jobRowFrame } from '../jobs/jobState'
import { formatSize } from './searchResult'

/** 兩顆篩選鍵，照這裡的先後排。 */
const FILTERS: readonly MediaJobFilter[] = ['open', 'all']

/**
 * 作品頁的「下載」段（M4 票 12，`.scratch/m4/media-downloads-shape.md`）：這部作品的每一筆 Job。
 *
 * 季表說的是貨架上有什麼，這一段是還在海上的那幾艘船與它們的艙單。**預設是還沒了結的**（使用者拍板）：
 * 在路上的，加上已入庫而還有檔案等人確認的；其餘在「全部」。一列與下載列表同一種（`JobSummary`），
 * 展開的是**檔案**而不是時間線——這一頁問的是「裡面有什麼、對到哪幾集」，時間線與動作在 `/jobs/:hash`。
 *
 * **這部作品從沒送過下載就整段不畫**：探索點進來的新作品不多一塊空殼。讀取中也不畫（同觀看區）。
 * 頁碼不進網址：作品頁的網址不為一段清單加參數。
 */
export function DownloadsPanel({ media }: { media: Media }) {
  const { t } = useTranslation()
  const headingId = useId()
  const [filter, setFilter] = useState<MediaJobFilter>('open')
  const [page, setPage] = useState(1)
  const listing = useQuery(mediaJobsQueryOptions(media.id, filter, page))
  useSeasonsFollow(media.id, listing.data)

  if (listing.isPending) return null
  if (!listing.data) {
    return (
      <section aria-labelledby={headingId} className="grid gap-4">
        <Heading id={headingId} />
        <div className="grid justify-items-start gap-3">
          <p className="max-w-prose text-sm text-ink-dim">{t('media.downloads.off')}</p>
          <GhostButton type="button" onClick={() => void listing.refetch()}>
            {t('media.downloads.retry')}
          </GhostButton>
        </div>
      </section>
    )
  }

  const shown = listing.data
  if (shown.counts.all === 0) return null
  // 換篩選時新的那一組回來之前手上是上一組的（`keepPreviousData`）：它的列不能掛在新的篩選鍵底下畫。
  const current = shown.filter === filter

  const choose = (next: MediaJobFilter) => {
    setFilter(next)
    setPage(1)
  }

  return (
    <section aria-labelledby={headingId} className="grid gap-4">
      <LiveJobs />
      <Heading id={headingId}>
        <nav aria-label={t('media.downloads.filters')} className="flex flex-wrap gap-2">
          {FILTERS.map((option) => {
            const label = t(`media.downloads.filter.${option}`, { count: shown.counts[option] })
            return option === filter ? (
              <span key={option} aria-current="true" className={`${FILTER_ACTIVE} text-ink`}>
                {label}
              </span>
            ) : (
              <button key={option} type="button" className={FILTER} onClick={() => choose(option)}>
                {label}
              </button>
            )
          })}
        </nav>
      </Heading>

      {current && <DownloadsPager listing={shown} onPage={setPage} />}

      {/* 翻過了最後一頁（翻頁的當下有幾筆入庫、離開了這一組）與這一組本來就是空的是兩件事：
          前者給回第一頁的路，後者只有「還沒了結」會是空的（「全部」空的時候整段不畫）。 */}
      {current && shown.jobs.length === 0 && shown.page > 1 && (
        <div className="grid justify-items-start gap-3">
          <p className="max-w-prose text-sm text-ink-dim">{t('jobs.emptyPage')}</p>
          <GhostButton type="button" onClick={() => setPage(1)}>
            {t('jobs.toFirstPage')}
          </GhostButton>
        </div>
      )}
      {current && shown.jobs.length === 0 && shown.page === 1 && (
        <p className="max-w-prose text-sm text-ink-dim">{t('media.downloads.noneOpen')}</p>
      )}

      {current && shown.jobs.length > 0 && (
        <div className="grid gap-2">
          {shown.jobs.map((job) => (
            <DownloadRow key={job.hash} job={job} />
          ))}
        </div>
      )}

      {current && shown.total > shown.page_size && (
        <DownloadsPager listing={shown} onPage={setPage} end />
      )}
    </section>
  )
}

/**
 * 推播掛在這一段上、有下載才掛（`useJobStream` 是一條長連線）：key 在 `['jobs', 'list']` 與
 * `['jobs', hash, 'files']` 底下，票 04 的合併失效自動涵蓋這一段。
 */
function LiveJobs() {
  useJobStream()
  return null
}

/**
 * **季表跟著這一段換狀態**（shape §7）：`GET /media/{id}` 的季表不被 SSE 失效，而這一段把「下載中」連到
 * 那一筆之後，兩塊並排說相反的話就藏不住了。看到**任何一筆換了狀態**就讓季表重問一次；進度變不算。
 *
 * 狀態變了有兩種看法，缺一不可：看得到的那幾列自己的狀態，以及件數——入庫之後那一列會離開「還沒了結」，
 * 那時候看得到的列裡已經沒有它了。**計劃出現也算**（`plan_id` 從 `null` 變成一個數）：下載中的 pre-plan
 * 是規劃器另外算的，Job 的狀態不動，而季表的「下載中」正是讀那一份（code-review 抓到）。
 *
 * 已知的鬆：不在這一頁、件數也沒變的那幾筆換了狀態看不到；換篩選時先拿到快取裡較舊的那一頁，會多問一次季表。
 */
function useSeasonsFollow(mediaId: string, listing: JobPage | undefined) {
  const queryClient = useQueryClient()
  const seen = useRef<{ counts: string; states: Map<string, string> } | null>(null)

  useEffect(() => {
    if (!listing) return
    const counts = JSON.stringify(listing.counts)
    const before = seen.current
    const moved =
      before !== null &&
      (before.counts !== counts ||
        listing.jobs.some((job) => {
          const was = before.states.get(job.hash)
          return was !== undefined && was !== standing(job)
        }))
    const states = new Map(before?.states)
    for (const job of listing.jobs) states.set(job.hash, standing(job))
    seen.current = { counts, states }
    if (moved) void queryClient.invalidateQueries({ queryKey: ['media', mediaId] })
  }, [listing, mediaId, queryClient])
}

/** 季表在乎的那兩件：狀態與有沒有計劃。進度不在裡面。 */
function standing(job: Job): string {
  return `${job.state}:${job.plan_id ?? ''}`
}

function Heading({ id, children }: { id: string; children?: ReactNode }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-2 border-b-2 border-rule-strong pb-2">
      <h2 id={id} className="label text-ink">
        {t('media.downloads.title')}
      </h2>
      {children}
    </div>
  )
}

/** 共用的 `Pager`（媒體庫的牆、下載列表）；這裡的鍵是按鈕，頁碼不進網址。 */
function DownloadsPager({
  listing,
  onPage,
  end = false,
}: {
  listing: JobPage
  onPage: (page: number) => void
  /** 清單底那一組。 */
  end?: boolean
}) {
  const { t } = useTranslation()
  const { page, page_size: size, total } = listing
  // 只有一頁時不畫：一行「1–3 / 3」在這一段只是雜訊，篩選鍵上已經有數字了。
  if (total <= size && page === 1) return null

  return (
    <Pager
      page={page}
      size={size}
      total={total}
      label={end ? t('media.downloads.pagesEnd') : t('media.downloads.pages')}
      announce={
        end
          ? undefined
          : (range) =>
              range.beyond
                ? t('jobs.rangeBeyond', { total })
                : t('jobs.range', { first: range.first, last: range.last, total })
      }
      link={(to, children) => (
        <button type="button" className={PAGE_LINK} onClick={() => onPage(to)}>
          {children}
        </button>
      )}
    />
  )
}

/**
 * 一筆下載：摘要與下載列表同一份，展開是它的檔案與一條去詳情頁的路。檔案**展開時才問**（`enabled`）：
 * 一包 BD 整季加字幕、字型可以上百個檔案，而多數列不會被展開。
 */
function DownloadRow({ job }: { job: Job }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)

  return (
    <details
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      className={jobRowFrame(job)}
    >
      <summary className="cursor-pointer list-none px-4 py-3">
        <JobSummary job={job} />
      </summary>
      <div className="grid gap-3 border-t-2 border-rule bg-hull px-4 py-3 [&>*]:min-w-0">
        {open && <JobFiles hash={job.hash} />}
        {/* 時間線、計劃與每一顆動作都在那一頁。 */}
        <Link to="/jobs/$hash" params={{ hash: job.hash }} className={GHOST_LINK}>
          {t('jobs.detail.open')}
        </Link>
      </div>
    </details>
  )
}

function JobFiles({ hash }: { hash: string }) {
  const { t, i18n } = useTranslation()
  const files = useQuery(jobFilesQueryOptions(hash, true))

  if (files.isPending) {
    return <p className="text-xs text-ink-dim">{t('media.downloads.files.loading')}</p>
  }
  if (!files.data) {
    return <p className="text-xs text-ink-dim">{t('media.downloads.files.off')}</p>
  }
  if (files.data.length === 0) {
    return <p className="max-w-prose text-xs text-ink-dim">{t('media.downloads.files.none')}</p>
  }

  return (
    <div className="grid gap-2">
      <h3 className="label text-ink-dim">{t('media.downloads.files.title')}</h3>
      <ul className="grid gap-px bg-rule">
        {files.data.map((file) => (
          <li
            key={file.rel_path}
            className="grid min-w-0 gap-1 bg-well px-3 py-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:gap-x-4"
          >
            {/* 檔名整行換行，不截斷：一包裡的幾個檔案常常只差最後那一段。 */}
            <span
              className={`value text-xs wrap-anywhere ${file.wanted ? 'text-ink' : 'text-ink-dim'}`}
            >
              {file.rel_path}
            </span>
            <span className="value flex flex-wrap items-center gap-x-2 text-xs text-ink-dim sm:justify-end">
              {placed(t, file).map((part, index) => (
                <Fragment key={part}>
                  {index > 0 && <Dot />}
                  <span className={file.action === 'import' ? 'text-ink' : undefined}>{part}</span>
                </Fragment>
              ))}
              <Dot />
              <span>{formatSize(file.size, i18n.language)}</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * 計劃把這個檔案放到哪裡：季集代號，不是正片時接著處置（特典、字幕、待審…，與檔案與版本同一組詞）——
 * 待審的那一份也有提案的季集，只印「待審」會把它藏起來。不下載的說「不下載」；計劃還沒算過是 `—`。
 * **中性的字，不塗漆**（The One Meaning Rule）。
 */
function placed(t: TFunction, file: JobFile): string[] {
  if (!file.wanted) return [t('media.downloads.files.unwanted')]
  if (file.action === null) return ['—']
  const code = formatEpisode(file)
  if (file.action === 'import') return [code || t('media.files.action.import')]
  const action = t(`media.files.action.${file.action}`)
  return code ? [code, action] : [action]
}
