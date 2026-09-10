import { useId, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import { queriesQueryOptions, searchTorrents } from '../api/search'
import { Notice, PrimaryButton } from '../components/controls'
import type { SetupStep } from '../api/schemas'
import { StepLine } from '../components/StepLine'
import { IndexerNotice } from './IndexerNotice'
import { RoutePicker } from './RoutePicker'
import { SearchResults } from './SearchResults'
import { sortRows, type SortKey } from './searchResult'

/**
 * 搜尋 torrent 與結果表（`.scratch/m1/search-results-shape.md`，票 08）。
 *
 * Media 詳情頁區塊序列的第 3 塊，往季集與檔案清單之間插進來，不重排前面兩區。
 *
 * **待命，按了才搜**（使用者 2026-09-10 拍板）：一次搜尋實測 35–85 秒，因為 Prowlarr 收到
 * 請求之後要現場去連它認得的每一個追蹤站。進頁面就自動搜等於替每個只想看季集表的人
 * 對五個公開站發五輪查詢。所以它是 mutation 不是 query——使用者按下去才發生的事。
 *
 * 按下之前畫面先列出**會送出去的那幾個關鍵字**（PRODUCT 原則 2：動手前先給看）。那份清單
 * 由後端算（`GET /api/search/queries`），不是前端重算一份——它要看快照的標題集合與 Route
 * 的 profile，兩邊各算一次遲早會給出不同的答案。
 */
export function SearchPanel({ media }: { media: Media }) {
  const { t } = useTranslation()
  const headingId = useId()
  const keywordId = useId()
  const sortId = useId()

  // `undefined` 是「這一輪還沒動過」，與刻意選「尚未指定」（`null`）不是同一件事。
  const [route, setRoute] = useState<number | null | undefined>(undefined)
  const chosen = route === undefined ? onlyChoice(media.routes) : route
  const [keyword, setKeyword] = useState('')
  const [sort, setSort] = useState<SortKey>('seeders')

  const planned = useQuery(queriesQueryOptions(media.id, chosen))
  const search = useMutation({
    mutationFn: () => searchTorrents({ media: media.id, q: keyword.trim(), route: chosen }),
  })

  const results = search.data
  const rows = results ? sortRows(results.rows, sort) : []

  return (
    <section className="grid gap-4" aria-labelledby={headingId}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b-2 border-rule-strong pb-2">
        <h2 id={headingId} className="label text-ink">
          {t('search.title')}
        </h2>
        {results && results.total > 0 && (
          <p className="value text-xs text-ink-dim">
            {results.total > rows.length
              ? t('search.countCapped', { total: results.total, shown: rows.length })
              : t('search.count', { count: results.total })}
          </p>
        )}
      </div>

      <form
        className="grid gap-3"
        onSubmit={(event) => {
          event.preventDefault()
          search.mutate()
        }}
      >
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,16rem)_auto] lg:items-end">
          <p className="grid gap-2">
            <label htmlFor={keywordId} className="label text-ink-dim">
              {t('search.keyword')}
            </label>
            <input
              id={keywordId}
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder={t('search.keywordPlaceholder')}
              className="value w-full border-2 border-rule bg-hull px-3 py-2.5 text-sm text-ink placeholder:text-ink-dim focus:border-rule-strong"
            />
          </p>
          <RoutePicker media={media} value={chosen} onChange={setRoute} />
          {/* 按鈕不停用（票 02b 的規則：按鈕永遠按得下去），只換文字。 */}
          <span className="lg:w-40">
            <PrimaryButton type="submit">
              {search.isPending ? t('search.submitting') : t('search.submit')}
            </PrimaryButton>
          </span>
        </div>

        <QueryPreview keyword={keyword} planned={planned.data?.queries} />
      </form>

      {search.isError && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('search.off')}
        </Notice>
      )}

      {/* 一次搜尋要 35–85 秒。那段時間裡畫面上要有東西在動，而這塊板子沒有 spinner——
          動的是纜繩：先鋪出要問的那幾個關鍵字（`working`），一有結果就換成筆數
          （shape brief §3 的焦點時刻，與精靈的靠泊序列是同一種東西）。 */}
      {(search.isPending || (results && results.attempts.length > 0)) && (
        <ol className="grid gap-2">
          {(results?.attempts ?? pending(keyword, planned.data?.queries)).map((attempt) => (
            <StepLine key={attempt.step} label={attempt.step} row={attempt} />
          ))}
        </ol>
      )}

      {results?.problem && <IndexerNotice problem={results.problem} detail={results.detail} />}

      {results && !results.problem && results.total === 0 && (
        <p className="max-w-prose text-sm text-ink-dim">
          {results.discarded > 0
            ? t('search.onlyOthers', { count: results.discarded })
            : t('search.empty')}
        </p>
      )}

      {/* 丟掉了幾筆不藏起來：索引站對搜不到的關鍵字會回它自己的熱門清單，而使用者
          有權知道那一千五百筆去了哪裡。 */}
      {results && results.total > 0 && results.discarded > 0 && (
        <p className="max-w-prose text-xs text-ink-dim">
          {t('search.discarded', { count: results.discarded })}
        </p>
      )}

      {rows.length > 0 && (
        <>
          {/* 窄版沒有欄頭，所以排序在這裡。兩個控制項改的是同一個值。 */}
          <p className="flex items-center gap-3 sm:hidden">
            <label htmlFor={sortId} className="label text-ink-dim">
              {t('search.sort.label')}
            </label>
            <select
              id={sortId}
              value={sort}
              onChange={(event) => setSort(event.target.value as SortKey)}
              className="value min-w-0 flex-1 border-2 border-rule bg-hull px-3 py-2 text-sm text-ink focus:border-rule-strong"
            >
              <option value="seeders">{t('search.column.seeders')}</option>
              <option value="size">{t('search.column.size')}</option>
            </select>
          </p>
          <SearchResults rows={rows} sort={sort} onSort={setSort} />
        </>
      )}

      {/* 整頁只有這一區塊的內容會變，看不見畫面的人得知道按下去發生了什麼。 */}
      <p aria-live="polite" className="sr-only">
        {results
          ? t('search.announce', { count: results.total, failed: failedCount(results) })
          : ''}
      </p>
    </section>
  )
}

/**
 * 按下去之前先給看：Berth 會拿哪幾個名字去問，以及這要花多久。
 *
 * 自己打了關鍵字時就只問那一個——他比 TMDB 更知道自己在找什麼，所以清單換成那一句。
 */
function QueryPreview({ keyword, planned }: { keyword: string; planned: string[] | undefined }) {
  const { t } = useTranslation()
  const typed = keyword.trim()

  return (
    <div className="grid gap-1">
      <p className="max-w-prose text-xs text-ink-dim">
        {typed ? t('search.willAskTyped') : t('search.willAsk')}
      </p>
      {/* 關鍵字是機器字串（送出去的就是它），走 `.value`。 */}
      <p className="value max-w-prose text-xs break-words text-ink">
        {typed || (planned ?? []).join(' · ') || '—'}
      </p>
      <p className="max-w-prose text-xs text-ink-dim">{t('search.slow')}</p>
    </div>
  )
}

/**
 * 還在問的時候那幾條纜繩長什麼樣：關鍵字就是要送出去的那幾個，狀態一律 `working`。
 *
 * 形狀與後端回的 `attempts` 相同，所以同一個 `StepLine` 畫得出來——一有結果就整批換掉，
 * 版面不跳。
 */
function pending(keyword: string, planned: string[] | undefined): SetupStep[] {
  const typed = keyword.trim()
  const steps = typed ? [typed] : (planned ?? [])
  return steps.map((step) => ({ step, status: 'running', detail: '', error: '' }))
}

/** 只有一條收得下這部作品的 Route 時就是它——沒有第二個選項的選擇不該讓使用者做。 */
function onlyChoice(routes: Media['routes']): number | null {
  return routes.length === 1 ? routes[0].id : null
}

function failedCount(results: { attempts: readonly { status: string }[] }): number {
  return results.attempts.filter((attempt) => attempt.status === 'failed').length
}
