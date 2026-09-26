import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import {
  addFeed,
  deleteFeed,
  parseRssRefusal,
  pollFeed,
  RSS_KEY,
  saveFeedExclusions,
  type Feed,
  type PollOutcome,
} from '../api/rss'
import { routesQueryOptions, type ManagedRoute } from '../api/routes'
import {
  ConfirmAction,
  Field,
  GHOST_LINK,
  GhostButton,
  Notice,
  PrimaryButton,
} from '../components/controls'
import { Dot } from '../components/Dot'
import { Timestamp } from '../components/Timestamp'
import { maskToken } from './maskToken'
import { RulesToggle } from './RulesEditor'
import { SectionHeading } from './SectionHeading'

/**
 * Feed 段（`.scratch/m3/rss-shape.md` §2 第 2 段）：新增表單與每一個 Feed。
 *
 * 間隔不在表單上（預設 15 分鐘，plan §3.2）；編輯與停用沒有消費者就不做（shape §6）。每一列有這個 Feed
 * 那一層的排除條件（票 10）。
 */
export function FeedSection({ feeds }: { feeds: Feed[] }) {
  const { t } = useTranslation()
  const headingId = useId()
  // 自動綁定送進哪一條（M3 票 21）：Feed 列說出它、新增表單讓人選。
  const routes = (useQuery(routesQueryOptions).data ?? []).map((row) => row.route)

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading
        id={headingId}
        label={t('rss.feeds.title')}
        count={{ value: feeds.length, spoken: t('rss.feeds.count', { count: feeds.length }) }}
      />
      {feeds.length === 0 && (
        // 空狀態（DESIGN.md）：一句 `ink` 散文加一條下一步。下一步在 Mikan 那一頭：訂閱之後才有網址可貼。
        <div className="grid gap-3 border-2 border-rule bg-well px-4 py-3">
          <p className="max-w-prose text-sm text-ink">{t('rss.feeds.empty')}</p>
          <a href="https://mikanani.me/" target="_blank" rel="noreferrer" className={GHOST_LINK}>
            {t('rss.feeds.toMikan')}
          </a>
        </div>
      )}
      {feeds.length > 0 && (
        <ul className="grid gap-3">
          {feeds.map((feed) => (
            <li key={feed.id} className="min-w-0">
              <FeedRow feed={feed} routes={routes} />
            </li>
          ))}
        </ul>
      )}
      <AddFeed routes={routes} />
    </section>
  )
}

type RouteRow = ManagedRoute['route']

function AddFeed({ routes }: { routes: RouteRow[] }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [route, setRoute] = useState<number | null>(null)
  const add = useMutation({
    mutationFn: () => addFeed(url.trim(), name.trim(), route),
    onSuccess: async () => {
      setUrl('')
      setName('')
      setRoute(null)
      await queryClient.invalidateQueries({ queryKey: RSS_KEY })
    },
  })
  const refusal = add.isError ? parseRssRefusal(add.error) : null

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (url.trim() !== '') add.mutate()
  }

  return (
    <form onSubmit={submit} className="grid gap-3 border-2 border-rule bg-well px-4 py-3">
      <p className="label text-ink-dim">{t('rss.feeds.add')}</p>
      <Field
        label={t('rss.feeds.url')}
        hint={t('rss.feeds.urlHint')}
        type="url"
        inputMode="url"
        autoComplete="off"
        spellCheck={false}
        required
        value={url}
        error={
          refusal ? t(`rss.refusal.${refusal.reason}`) : add.isError ? t('rss.failed') : undefined
        }
        onChange={(event) => setUrl(event.target.value)}
      />
      <Field
        label={t('rss.feeds.name')}
        hint={t('rss.feeds.nameHint')}
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <FeedRoutePicker routes={routes} value={route} onChange={setRoute} />
      <div className="sm:max-w-xs">
        <PrimaryButton type="submit" busy={add.isPending} disabled={url.trim() === ''}>
          {add.isPending ? t('rss.feeds.adding') : t('rss.feeds.addAction')}
        </PrimaryButton>
      </div>
    </form>
  )
}

/** 那一列不在畫面內時捲到它（在畫面內就不動，免得每按一次都跳一下）。 */
function bringBack(element: HTMLElement | null) {
  if (!element) return
  const box = element.getBoundingClientRect()
  if (box.top < 0 || box.bottom > window.innerHeight) element.scrollIntoView({ block: 'nearest' })
}

/**
 * 自動綁定送進的 Route（M3 票 21，照 Sonarr Import List 的 Root Folder）。只列啟用中的：停用的
 * 那一條自動綁定本來就不看。只有一條啟用中的 Route 時不必選，這一欄不出現。
 */
function FeedRoutePicker({
  routes,
  value,
  onChange,
}: {
  routes: RouteRow[]
  value: number | null
  onChange: (route: number | null) => void
}) {
  const { t } = useTranslation()
  const id = useId()
  const enabled = routes.filter((row) => row.enabled)
  if (enabled.length < 2) return null

  return (
    <p className="grid gap-2">
      <label htmlFor={id} className="label text-ink-dim">
        {t('rss.feeds.route')}
      </label>
      <select
        id={id}
        aria-describedby={`${id}-hint`}
        value={value ?? ''}
        onChange={(event) =>
          onChange(event.target.value === '' ? null : Number(event.target.value))
        }
        className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
      >
        <option value="">{t('rss.feeds.routeNone')}</option>
        {enabled.map((row) => (
          <option key={row.id} value={row.id}>
            {row.name}
          </option>
        ))}
      </select>
      <span id={`${id}-hint`} className="text-xs text-ink-dim">
        {t('rss.feeds.routeHint')}
      </span>
    </p>
  )
}

function FeedRow({ feed, routes }: { feed: Feed; routes: RouteRow[] }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  const [polled, setPolled] = useState<PollOutcome | null>(null)
  const self = useRef<HTMLElement>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: RSS_KEY })
  const poll = useMutation({
    mutationFn: () => pollFeed(feed.id),
    onMutate: () => setPolled(null),
    onSuccess: async (outcome) => {
      setPolled(outcome)
      await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: ['jobs'] })])
      // 需要人的那幾段浮在頁首（第一輪、待綁定），這一輪長出來的會把這一列連同結果句推出畫面
      // （M3 票 21 的 audit：390px 上從 y 356 推到 2443）。重畫之後捲回來。
      requestAnimationFrame(() => bringBack(self.current))
    },
  })
  const remove = useMutation({ mutationFn: () => deleteFeed(feed.id), onSuccess: refresh })
  const routeName = routes.find((row) => row.id === feed.route_id)?.name

  return (
    <article
      ref={self}
      tabIndex={-1}
      aria-labelledby={headingId}
      className={`grid gap-2 border-2 bg-well px-4 py-3 ${
        feed.last_error ? 'border-rule-strong' : 'border-rule'
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="label bg-deck px-2 py-1.5 text-ink">{t(`rss.kind.${feed.kind}`)}</span>
        <h3 id={headingId} className="value min-w-0 wrap-anywhere text-ink">
          {feed.name}
        </h3>
      </div>
      {/* 聚合 feed 的 token 就是憑證：畫面上不整串印出來（`maskToken`）。 */}
      <p className="value text-xs wrap-anywhere text-ink-dim">{maskToken(feed.url)}</p>
      <p className="text-xs text-ink-dim">
        {t('rss.feeds.every', { minutes: Math.round(feed.interval_sec / 60) })} <Dot />{' '}
        {t('rss.feeds.polled')} <Timestamp at={feed.last_polled_at} /> <Dot />{' '}
        <span className="value">{t('rss.feeds.items', { count: feed.items })}</span>
        {routeName !== undefined && (
          <>
            {' '}
            <Dot /> {t('rss.feeds.sendsTo')} <span className="value">{routeName}</span>
          </>
        )}
      </p>
      {/* 第一輪還沒選：決定在頁首那一段（票 11），這裡只說一聲為什麼一筆都沒送。 */}
      {feed.primed_at === null && <p className="text-xs text-ink">{t('rss.feeds.undecided')}</p>}
      {feed.last_error && (
        <Notice signal="assigned" label={t('rss.feeds.failed')}>
          <span className="value text-xs wrap-anywhere">{feed.last_error}</span>
        </Notice>
      )}
      <p role="status" className="text-xs text-ink">
        {/* 這一輪抓不到 Feed 時不說「新 0 筆」：那是沒讀到，不是讀到了沒有新的。原文在上面那一塊。 */}
        {polled &&
          (polled.failed
            ? t('rss.feeds.polledFailed')
            : t('rss.feeds.polledNow', {
                items: polled.items,
                series: polled.series,
                bound: polled.bound,
                sent: polled.submitted,
              }))}
      </p>
      {(poll.isError || remove.isError) && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('rss.failed')}
        </Notice>
      )}
      <RulesToggle
        rules={feed.exclusions}
        save={(rules) => saveFeedExclusions(feed.id, rules)}
        lede={t('rss.rules.feedLede')}
      />
      <div className="flex flex-wrap items-start gap-2">
        <GhostButton type="button" busy={poll.isPending} onClick={() => poll.mutate()}>
          {poll.isPending ? t('rss.feeds.polling') : t('rss.feeds.poll')}
        </GhostButton>
        <ConfirmAction
          label={t('rss.feeds.delete')}
          confirmLabel={t('rss.feeds.deleteConfirm')}
          warning={t('rss.feeds.deleteWarning', { count: feed.items })}
          pending={remove.isPending}
          pendingLabel={t('rss.feeds.deleting')}
          onConfirm={() => remove.mutate()}
        />
      </div>
    </article>
  )
}
