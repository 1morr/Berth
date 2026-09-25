import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import {
  exclusionsQueryOptions,
  feedsQueryOptions,
  itemsQueryOptions,
  RSS_KEY,
  saveSeriesExclusions,
  seriesQueryOptions,
  unbindSeries,
  type FeedItem,
  type RssSeries,
} from '../api/rss'
import { ConfirmAction, Notice, PAGE_TITLE } from '../components/controls'
import { Dot } from '../components/Dot'
import { DetailLine, QueueRow } from '../components/QueueRow'
import { whenText } from '../components/queueText'
import { SIGNAL_FILL } from '../components/signal'
import { useFocusAfterRemoval } from '../components/useFocusAfterRemoval'
import { displayRound } from '../i18n/displayRound'
import { JobLink } from '../jobs/JobLink'
import { ExclusionsSection } from '../rss/ExclusionsSection'
import { FeedSection } from '../rss/FeedSection'
import { FirstRoundSection } from '../rss/FirstRoundSection'
import { Grounds } from '../rss/GroundsList'
import { RulesToggle } from '../rss/RulesEditor'
import { SectionHeading } from '../rss/SectionHeading'
import { SeriesBinder } from '../rss/SeriesBinder'
import { skipText } from '../rss/skip'

/**
 * RSS `/rss`（`.scratch/m3/rss-shape.md`，M3 票 08）。只有 admin。
 *
 * 單頁堆疊，由上而下：**等你決定**（新搜尋 feed 的第一輪，票 11）與**待綁定**（有才出現，需要你的事
 * 浮到最上面）→ Feed → 全域的排除條件
 * （票 10）→ 綁好的 RSS Series → 最近的 Feed Item。平常它在背景輪詢，人只在有新的 RSS Series 等綁定時回來——所以第一個
 * viewport 回答的是「有沒有要我綁的」。
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
          {exclusions.data && <ExclusionsSection exclusions={exclusions.data} />}
          {bound.length > 0 && <Bound rows={bound} onDone={setSaid} />}
          {/* 沒有 Feed 時整頁只有 Feed 段（shape §5）：還不會有任何 Item。 */}
          {(feeds.data ?? []).length > 0 && <Items rows={items.data ?? []} />}
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
              when={sourceOf(row)}
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

function Bound({ rows, onDone }: { rows: RssSeries[]; onDone: (said: string) => void }) {
  const { t } = useTranslation()
  const headingId = useId()

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading
        id={headingId}
        label={t('rss.bound.title')}
        count={{ value: rows.length, spoken: t('rss.bound.count', { count: rows.length }) }}
      />
      <ul className="grid gap-3">
        {rows.map((row) => (
          <li key={row.id} className="min-w-0">
            <BoundRow row={row} onDone={onDone} />
          </li>
        ))}
      </ul>
    </section>
  )
}

function BoundRow({ row, onDone }: { row: RssSeries; onDone: (said: string) => void }) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  const unbind = useMutation({
    mutationFn: () => unbindSeries(row.id),
    onSuccess: async () => {
      onDone(t('rss.bound.unbound'))
      await queryClient.invalidateQueries({ queryKey: RSS_KEY })
    },
  })
  const title =
    displayRound(i18n.language, { 'zh-Hant': row.media_title, en: row.media_title_en }) ||
    row.media_id
  const automatic = row.bound_by === 'system'

  return (
    <article
      tabIndex={-1}
      aria-labelledby={headingId}
      className="grid gap-2 border-2 border-rule bg-well px-4 py-3"
    >
      <h3 id={headingId} className="value min-w-0 wrap-anywhere text-ink">
        {title}
      </h3>
      <p className="value text-xs wrap-anywhere text-ink-dim">{row.title_raw}</p>
      <p className="text-xs text-ink-dim">
        {automatic && (
          <>
            {t('rss.bound.automatic')} <Dot />{' '}
          </>
        )}
        {t('rss.bound.route', { route: row.route_name || '—' })} <Dot />{' '}
        <span className="value">{sourceOf(row)}</span>
        {row.season !== null && (
          <>
            {' '}
            <Dot /> <span className="value">{t('rss.bound.season', { season: row.season })}</span>
          </>
        )}
        {row.episode_offset !== null && (
          <>
            {' '}
            <Dot />{' '}
            <span className="value">{t('rss.bound.offset', { offset: row.episode_offset })}</span>
          </>
        )}
      </p>
      {/* 沒有人選過這一部：綁好的那一列要說得出憑什麼（票 09）。 */}
      {automatic && <Grounds lead={t('rss.bound.grounds')} reasons={row.reasons} />}
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
    </article>
  )
}

/** 這個 RSS Series 那一層的排除條件（票 10）。待綁定的也有：綁定之前就擋得下不要的那幾集。 */
function SeriesRules({ row }: { row: RssSeries }) {
  const { t } = useTranslation()
  return (
    <RulesToggle
      rules={row.exclusions}
      save={(rules) => saveSeriesExclusions(row.id, rules)}
      lede={t('rss.rules.seriesLede')}
    />
  )
}

function SeriesDetails({ row }: { row: RssSeries }) {
  const { t } = useTranslation()
  const page =
    row.mikan_bangumi_id !== null
      ? `https://mikanani.me/Home/Bangumi/${row.mikan_bangumi_id}${
          row.mikan_subgroup_id !== null ? `#${row.mikan_subgroup_id}` : ''
        }`
      : null
  return (
    <>
      <DetailLine term={t('rss.series.key')}>{row.key}</DetailLine>
      {page !== null && (
        <DetailLine term={t('rss.series.page')}>
          <a
            href={page}
            target="_blank"
            rel="noreferrer"
            className="underline decoration-rule-strong underline-offset-4 hover:decoration-ink"
          >
            {page}
          </a>
        </DetailLine>
      )}
    </>
  )
}

function Items({ rows }: { rows: FeedItem[] }) {
  const { t, i18n } = useTranslation()
  const headingId = useId()

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
            <li key={row.id} className="grid min-w-0 gap-1 bg-well px-4 py-2.5">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <ItemChip row={row} />
                <span className="value min-w-0 basis-full text-sm wrap-anywhere text-ink sm:flex-1 sm:basis-auto">
                  {row.title}
                </span>
              </div>
              <p className="text-xs text-ink-dim">
                {t('rss.items.published')}{' '}
                <span className="value">
                  {row.published_at ? whenText(row.published_at, i18n.language) : '—'}
                </span>
                {row.job_hash && (
                  <>
                    {' '}
                    <Dot /> <JobLink hash={row.job_hash}>{t('rss.items.job')}</JobLink>
                  </>
                )}
              </p>
              {/* 排除與去重擋下的都不是錯誤（票 10）：一句「為什麼沒下載」，不塗漆。 */}
              {row.skip && (
                <p className="max-w-prose text-xs wrap-anywhere text-ink-dim">
                  {skipText(t, row.skip)}
                </p>
              )}
              {row.error && <p className="value text-xs wrap-anywhere text-ink">{row.error}</p>}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/**
 * 一筆 Item 的狀態色塊。**常態不塗漆**：待綁定已經在第一段塗過了，已送單是沒事，已排除與重複是
 * 照使用者的規則與帳本擋下的（票 10，不是錯誤）；只有送不出去
 * （`matched` 帶著原文）塗 `assigned`——卡住了、下一輪會再送，但原因（Route 紅燈、磁碟門檻）
 * 多半要人去修（DESIGN.md：卡住是 `assigned`，`blocked` 留給失敗）。
 */
function ItemChip({ row }: { row: FeedItem }) {
  const { t } = useTranslation()
  const stuck = row.status === 'matched' && row.error !== ''
  const key = stuck ? 'stuck' : row.status
  return (
    <span className={`label px-2 py-1 ${stuck ? SIGNAL_FILL.assigned : SIGNAL_FILL.neutral}`}>
      {t(`rss.items.status.${key}`)}
    </span>
  )
}

function sourceOf(row: RssSeries): string {
  return row.mikan_bangumi_id !== null
    ? `Mikan ${row.mikan_bangumi_id} × ${row.mikan_subgroup_id ?? '?'}`
    : row.key
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
