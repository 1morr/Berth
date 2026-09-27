import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  RSS_KEY,
  saveSeriesExclusions,
  seriesItemsQueryOptions,
  unbindSeries,
  type RssSeries,
} from '../api/rss'
import { ConfirmAction, GhostButton, Notice } from '../components/controls'
import { Dot } from '../components/Dot'
import { episodeCode } from '../components/episodes'
import { ExpandHint } from '../components/ExpandHint'
import { SIGNAL_FILL } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import { firstBatchAskText } from './firstBatchAsk'
import { Grounds } from './GroundsList'
import { ItemLine } from './ItemLine'
import { RulesToggle } from './RulesEditor'
import { SectionHeading } from './SectionHeading'
import {
  byWork,
  groupName,
  mikanPage,
  sourceLabel,
  workTitle,
  type WorkGroup,
} from './seriesByWork'

/**
 * 綁好的 RSS Series，以作品呈現（M4 票 13，`.scratch/m4/rss-series-shape.md`）：作品一塊、字幕組一列；
 * 完結的收在段尾預設收起的「已完結」（紀錄照舊，新的一筆出現時後端說它沒完結，它就回到上面）。
 *
 * 一列說得出這個字幕組下了什麼（已入庫 / 下載中 / 排除）與最近發佈的是哪一集；展開看它的每一筆 Item。
 * Series 層的排除條件、季號與 offset、解除綁定收在展開區的「進階」——多半只想要 Feed 層的（試跑回饋）。
 */
export function SeriesSection({
  rows,
  onDone,
}: {
  rows: RssSeries[]
  onDone: (said: string) => void
}) {
  const { t } = useTranslation()
  const headingId = useId()
  const { active, finished } = byWork(rows)
  const following = active.reduce((sum, work) => sum + work.rows.length, 0)
  const done = finished.reduce((sum, work) => sum + work.rows.length, 0)

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading
        id={headingId}
        label={t('rss.bound.title')}
        count={{ value: following, spoken: t('rss.bound.count', { count: following }) }}
      />
      {active.length === 0 ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('rss.bound.allFinished')}</p>
      ) : (
        <Works works={active} onDone={onDone} />
      )}
      {finished.length > 0 && (
        <details className="group">
          <summary className="flex min-h-6 w-fit cursor-pointer items-center gap-2 marker:content-none">
            <span className="label text-ink">{t('rss.bound.finished', { count: done })}</span>
            <ExpandHint />
          </summary>
          <p className="mt-2 max-w-prose text-sm text-ink-dim">{t('rss.bound.finishedLede')}</p>
          <div className="mt-3">
            <Works works={finished} onDone={onDone} />
          </div>
        </details>
      )}
    </section>
  )
}

function Works({ works, onDone }: { works: WorkGroup[]; onDone: (said: string) => void }) {
  return (
    <ul className="grid gap-3">
      {works.map((work) => (
        <li key={work.mediaId} className="min-w-0">
          <Work work={work} onDone={onDone} />
        </li>
      ))}
    </ul>
  )
}

/** 一部作品：標題帶作品名與 Route，底下每個字幕組一列。 */
function Work({ work, onDone }: { work: WorkGroup; onDone: (said: string) => void }) {
  const { i18n } = useTranslation()
  const headingId = useId()
  const title = workTitle(i18n.language, work.lead)

  return (
    <article aria-labelledby={headingId} className="grid border-2 border-rule bg-rule">
      <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 bg-deck px-4 py-2.5">
        <h3 id={headingId} className="value min-w-0 wrap-anywhere text-ink">
          {title}
        </h3>
        {work.routes.length > 0 && (
          <span className="value text-xs text-ink-dim">{work.routes.join(' · ')}</span>
        )}
      </header>
      <ul className="grid gap-px">
        {work.rows.map((row) => (
          <li key={row.id} className="min-w-0 bg-well">
            <SeriesRow row={row} title={title} onDone={onDone} />
          </li>
        ))}
      </ul>
    </article>
  )
}

function SeriesRow({
  row,
  title,
  onDone,
}: {
  row: RssSeries
  title: string
  onDone: (said: string) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  const hintId = useId()
  const [open, setOpen] = useState(false)
  const unbind = useMutation({
    mutationFn: () => unbindSeries(row.id),
    onSuccess: async () => {
      onDone(t('rss.bound.unbound'))
      await queryClient.invalidateQueries({ queryKey: RSS_KEY })
    },
  })
  const automatic = row.bound_by === 'system'
  const group = groupName(row)
  const page = mikanPage(row)
  const source = sourceLabel(t, row, { group: false })

  return (
    // `tabIndex={-1}`：解除綁定之後這一列離開這一段，焦點落在接替的那一列（`useFocusAfterRemoval`）。
    <article tabIndex={-1} aria-labelledby={headingId} className="grid gap-2 px-4 py-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h4 id={headingId} className="value min-w-0 wrap-anywhere text-ink">
          {group || '—'}
        </h4>
        {page !== null ? (
          <a
            href={page}
            target="_blank"
            rel="noreferrer"
            className="text-xs wrap-anywhere text-ink-dim underline decoration-rule-strong underline-offset-4 hover:text-ink hover:decoration-ink"
          >
            {source}
          </a>
        ) : (
          <span className="text-xs text-ink-dim">{source}</span>
        )}
      </div>

      <p className="text-xs text-ink-dim">
        <Count label={t('rss.bound.imported', { n: row.imported })} /> <Dot />{' '}
        <Count label={t('rss.bound.active', { n: row.active })} /> <Dot />{' '}
        <Count label={t('rss.bound.excluded', { n: row.excluded })} /> <Dot /> <Latest row={row} />
        {automatic && (
          <>
            {' '}
            <Dot /> {t('rss.bound.automatic')}
          </>
        )}
      </p>

      {/* 第一批還在等人（M4 票 11）：與作品頁、審核頁那一組說同一句。 */}
      {!row.confirmed && row.ask && (
        <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs text-ink">
          <span className={`label px-2 py-1 ${SIGNAL_FILL.assigned}`}>
            {t('rss.subscribe.firstBatch')}
          </span>
          <span className="max-w-prose">
            {firstBatchAskText(t, { title, group, ask: row.ask })}
          </span>
        </p>
      )}

      <details onToggle={(event) => setOpen(event.currentTarget.open)}>
        <summary
          aria-labelledby={`${hintId} ${headingId}`}
          className="flex min-h-6 w-fit cursor-pointer items-center marker:content-none"
        >
          <span id={hintId}>
            <ExpandHint open={open} />
          </span>
        </summary>
        <div className="mt-2 grid gap-3">
          {/* 沒有人選過這一部：說得出憑什麼綁上（票 09）。 */}
          {automatic && <Grounds lead={t('rss.bound.grounds')} reasons={row.reasons} />}
          <SeriesItems series={row.id} enabled={open} />
          <div className="grid gap-2 border-t-2 border-rule pt-3">
            <p className="label text-ink-dim">{t('rss.bound.advanced')}</p>
            {(row.season !== null || row.episode_offset !== null) && (
              <p className="text-xs text-ink-dim">
                {row.season !== null && (
                  <span className="value">{t('rss.bound.season', { season: row.season })}</span>
                )}
                {row.season !== null && row.episode_offset !== null && (
                  <>
                    {' '}
                    <Dot />{' '}
                  </>
                )}
                {row.episode_offset !== null && (
                  <span className="value">
                    {t('rss.bound.offset', { offset: row.episode_offset })}
                  </span>
                )}
              </p>
            )}
            <SeriesRules row={row} />
            {unbind.isError && (
              <Notice signal="blocked" label={t('common.failed')}>
                {t('rss.failed')}
              </Notice>
            )}
            <div className="flex flex-wrap items-start gap-2">
              <ConfirmAction
                label={t('rss.bound.unbind')}
                confirmLabel={t('rss.bound.unbindConfirm')}
                warning={t('rss.bound.unbindWarning')}
                pending={unbind.isPending}
                pendingLabel={t('rss.bound.unbinding')}
                onConfirm={() => unbind.mutate()}
              />
            </div>
          </div>
        </div>
      </details>
    </article>
  )
}

/** 這個 RSS Series 那一層的排除條件（票 10）。待綁定那一列也用它：綁定之前就擋得下不要的那幾集。 */
export function SeriesRules({ row }: { row: RssSeries }) {
  const { t } = useTranslation()
  return (
    <RulesToggle
      rules={row.exclusions}
      save={(rules) => saveSeriesExclusions(row.id, rules)}
      lede={t('rss.rules.seriesLede')}
    />
  )
}

/**
 * 「已入庫 11」：整句是一格翻好的字（語序各語言不同，數字拆不出來），所以整格走 `.value` 的等寬數字；不塗漆，
 * 件數是中性的事實。
 */
function Count({ label }: { label: string }) {
  return <span className="value">{label}</span>
}

/** 「最近 E12 · 3 天前」：最近**發佈**的那一筆，不是長出這個 Series 的那一筆（`title_raw`）。 */
function Latest({ row }: { row: RssSeries }) {
  const { t } = useTranslation()
  if (row.latest_at === null && !row.latest_title) return <>{t('rss.bound.nothingYet')}</>
  return (
    <span title={row.latest_title}>
      {row.latest_episode !== null
        ? t('rss.bound.latest', { episode: episodeCode(row.latest_episode) })
        : t('rss.bound.latestUnnumbered')}
      {row.latest_at !== null && (
        <>
          {' '}
          <Dot /> <Timestamp at={row.latest_at} />
        </>
      )}
    </span>
  )
}

/** 展開之後才讀：一頁 10–40 個 Series，每個先讀一次它的 Item 是白打。 */
function SeriesItems({ series, enabled }: { series: number; enabled: boolean }) {
  const { t } = useTranslation()
  const items = useQuery({ ...seriesItemsQueryOptions(series), enabled })

  if (!enabled) return null
  return (
    <div className="grid gap-2">
      <p className="label text-ink-dim">{t('rss.bound.items')}</p>
      {items.isPending ? (
        <p className="text-sm text-ink-dim">{t('rss.bound.itemsLoading')}</p>
      ) : items.isError ? (
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm text-ink-dim">{t('rss.bound.itemsOff')}</p>
          <GhostButton type="button" onClick={() => void items.refetch()}>
            {t('rss.bound.itemsRetry')}
          </GhostButton>
        </div>
      ) : items.data.length === 0 ? (
        <p className="text-sm text-ink-dim">{t('rss.bound.itemsEmpty')}</p>
      ) : (
        <ul className="grid gap-px border-2 border-rule bg-rule">
          {items.data.map((row) => (
            <ItemLine key={row.id} row={row} />
          ))}
        </ul>
      )}
    </div>
  )
}
