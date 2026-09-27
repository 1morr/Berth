import { useQuery } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  exclusionsQueryOptions,
  feedsQueryOptions,
  itemsQueryOptions,
  seriesQueryOptions,
  type Feed,
  type FeedItem,
  type RssSeries,
} from '../api/rss'
import { PAGE_TITLE } from '../components/controls'
import { Dot } from '../components/Dot'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { SIGNAL_FILL } from '../components/signal'
import { useFocusAfterRemoval } from '../components/useFocusAfterRemoval'
import { ExclusionsSection } from '../rss/ExclusionsSection'
import { FeedSection } from '../rss/FeedSection'
import { FirstRoundSection } from '../rss/FirstRoundSection'
import { Grounds } from '../rss/GroundsList'
import { ItemLine } from '../rss/ItemLine'
import { OneshotSection } from '../rss/OneshotSection'
import { SectionHeading } from '../rss/SectionHeading'
import { SeriesBinder } from '../rss/SeriesBinder'
import { groupName, mikanPage, sourceLabel, workTitle } from '../rss/seriesByWork'
import { SeriesRules, SeriesSection } from '../rss/SeriesSection'

/**
 * RSS `/rss`（`.scratch/m3/rss-shape.md`，M3 票 08）。只有 admin。
 *
 * 單頁堆疊，由上而下：**等你決定**（新搜尋 feed 的第一輪，票 11）與**待綁定**（有才出現，需要你的事
 * 浮到最上面）→ Feed → 一次性 RSS 連結（票 18，不建 Feed，所以沒有 Feed 時也在）→ 全域的排除條件
 * （票 10）→ 綁好的 RSS Series（以作品呈現、完結的收起，M4 票 13）→ 最近的 Feed Item。平常它在背景輪詢，人只在
 * 有新的 RSS Series 等綁定時回來——所以第一個 viewport 回答的是「有沒有要我綁的」。
 */
export function RssPage() {
  const { t } = useTranslation()
  const feeds = useQuery(feedsQueryOptions())
  const series = useQuery(seriesQueryOptions())
  const items = useQuery(itemsQueryOptions())
  const exclusions = useQuery(exclusionsQueryOptions())
  const frame = useFocusAfterRemoval()
  // 綁完那一列會離開待綁定段（The Focus Takes The Next Row Rule）：這一句給看不見畫面的人。
  const [said, setSaid] = useState('')

  const undecided = (feeds.data ?? []).filter((feed) => feed.primed_at === null)
  const pending = (series.data ?? []).filter((row) => row.media_id === null)
  const bound = (series.data ?? []).filter((row) => row.media_id !== null)
  const loading = feeds.isPending || series.isPending || items.isPending || exclusions.isPending
  const off = !loading && (!feeds.data || !series.data || !items.data || !exclusions.data)

  return (
    <div ref={frame} className="mx-auto grid w-full max-w-[80rem] gap-8 px-6 py-8">
      <div className="border-b-2 border-rule-strong pb-2">
        <h1 tabIndex={-1} className={PAGE_TITLE}>
          {t('rss.title')}
        </h1>
      </div>

      <p aria-live="polite" className="sr-only">
        {said}
      </p>

      {loading ? (
        <Loading />
      ) : off ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('rss.off')}</p>
      ) : (
        <>
          {undecided.length > 0 && <FirstRoundSection feeds={undecided} onDone={setSaid} />}
          {pending.length > 0 && <Pending rows={pending} onDone={setSaid} />}
          <FeedSection feeds={feeds.data ?? []} />
          <OneshotSection />
          {exclusions.data && <ExclusionsSection exclusions={exclusions.data} />}
          {bound.length > 0 && <SeriesSection rows={bound} onDone={setSaid} />}
          {/* 沒有 Feed 時整頁只有 Feed 段（shape §5）：還不會有任何 Item。 */}
          {(feeds.data ?? []).length > 0 && (
            <Items rows={items.data ?? []} feeds={feeds.data ?? []} series={series.data ?? []} />
          )}
        </>
      )}
    </div>
  )
}

function Pending({ rows, onDone }: { rows: RssSeries[]; onDone: (said: string) => void }) {
  const { t } = useTranslation()
  const headingId = useId()

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading
        id={headingId}
        label={t('rss.pending.title')}
        extra={
          // 整頁唯一的一塊漆：它就是這一頁要你做的事（Needs-You Floats Up）。
          <span className={`label px-2 py-1 ${SIGNAL_FILL.assigned}`}>
            {t('rss.pending.chip', { count: rows.length })}
          </span>
        }
      />
      <p className="max-w-prose text-sm text-ink-dim">{t('rss.pending.lede')}</p>
      <ul className="grid gap-3">
        {rows.map((row) => (
          <li key={row.id} className="min-w-0">
            <QueueRow
              label={t('rss.pending.label')}
              title={row.title_raw}
              heading="h3"
              sentence={t('rss.pending.waiting', { count: row.waiting })}
              when={sourceLabel(t, row)}
              // 自動綁定查過、沒綁上的理由（票 09）。它回答「為什麼要我來綁」，所以不收進展開區。
              body={
                <>
                  <Grounds lead={t('rss.pending.why')} reasons={row.reasons} />
                  <SeriesRules row={row} />
                </>
              }
              refusal={null}
              details={<SeriesDetails row={row} />}
            >
              <SeriesBinder series={row} onDone={onDone} />
            </QueueRow>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** 認不出是哪一部時去 Mikan 的番組頁看。連結的字是名字：鍵與 id 是內部編號，不印（M4 票 13）。 */
function SeriesDetails({ row }: { row: RssSeries }) {
  const { t } = useTranslation()
  const page = mikanPage(row)
  if (page === null) return null
  return (
    <DetailLine term={t('rss.series.page')}>
      <a
        href={page}
        target="_blank"
        rel="noreferrer"
        className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
      >
        {sourceLabel(t, row)}
      </a>
    </DetailLine>
  )
}

function Items({ rows, feeds, series }: { rows: FeedItem[]; feeds: Feed[]; series: RssSeries[] }) {
  const { t, i18n } = useTranslation()
  const headingId = useId()
  const feedOf = new Map(feeds.map((feed) => [feed.id, feed]))
  const seriesOf = new Map(series.map((row) => [row.id, row]))

  /** 「來自 Mikan · 與妳相戀到生命盡頭 × LoliHouse」；沒綁的說待綁定（M4 票 13）。 */
  function source(row: FeedItem) {
    const owner = row.series_id !== null ? seriesOf.get(row.series_id) : undefined
    const work =
      owner && owner.media_id !== null
        ? t('rss.items.work', {
            work: workTitle(i18n.language, owner),
            group: groupName(owner) || '—',
          })
        : t('rss.items.unbound')
    return (
      <>
        {t('rss.items.from')}{' '}
        <span className="value text-ink">{feedOf.get(row.feed_id)?.name ?? '—'}</span> <Dot />{' '}
        {work}
      </>
    )
  }

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading
        id={headingId}
        label={t('rss.items.title')}
        count={{ value: rows.length, spoken: t('rss.items.count', { count: rows.length }) }}
      />
      {rows.length === 0 ? (
        <p className="max-w-prose text-sm text-ink-dim">{t('rss.items.empty')}</p>
      ) : (
        <ul className="grid gap-px bg-rule">
          {rows.map((row) => (
            <ItemLine key={row.id} row={row} source={source(row)} />
          ))}
        </ul>
      )}
    </section>
  )
}

/** 讀取中的佔位：不動的色條（DESIGN.md，沒有骨架屏動畫）。 */
function Loading() {
  return (
    <div className="grid gap-3" aria-hidden="true">
      <div className="h-24 border-2 border-rule bg-well" />
      <div className="h-40 border-2 border-rule bg-well" />
    </div>
  )
}
