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
  setFeedRoutes,
  type Feed,
  type FeedRoutesOutcome,
  type KindRoutes,
  type PollOutcome,
} from '../api/rss'
import { routesQueryOptions } from '../api/routes'
import type { MediaKind, RouteView } from '../api/schemas'
import { ConfirmPanel } from '../components/ConfirmPanel'
import {
  CONFIRM_ACTIONS,
  ConfirmAction,
  Field,
  GHOST_LINK,
  GhostButton,
  Notice,
  PrimaryButton,
} from '../components/controls'
import { Dot } from '../components/Dot'
import { RequestFailed } from '../components/RequestFailed'
import { Timestamp } from '../components/Timestamp'
import { useInPlaceConfirm } from '../components/useInPlaceConfirm'
import { bindsNow, complete, KINDS, prefilled, routesFor, routesOf, unsetKinds } from './feedRoutes'
import { maskToken } from './maskToken'
import { RulesFields, RulesToggle } from './RulesEditor'
import { rssProblem } from './rssProblem'
import { SectionHeading } from '../components/SectionHeading'

/**
 * Feed 段（`.scratch/m3/rss-shape.md` §2 第 2 段）：新增表單與每一個 Feed。
 *
 * 間隔不在表單上（預設 15 分鐘，plan §3.2）；編輯與停用沒有消費者就不做（shape §6）。每一列有這個 Feed
 * 那一層的排除條件（票 10）。
 */
export function FeedSection({ feeds }: { feeds: Feed[] }) {
  const { t } = useTranslation()
  const headingId = useId()
  // 自動綁定送進哪一條，劇集、電影各一條（M3 票 21、M4 票 105）：Feed 列說出它們、新增表單讓人選。
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

/**
 * 新增 Feed 的表單。排除條件也在這裡（M4 票 110）：Mikan 不預覽、加入後半分鐘內第一輪就綁定送單，
 * 加完再到卡片上設的擋不到已經送出的。規則先記在表單裡，跟著 `POST /rss/feeds` 一起送。
 *
 * 規則那一塊有自己的 `<form>`（Enter 加一條），所以放在主表單外面，「加入」以 `form` 屬性接回主表單。
 */
function AddFeed({ routes }: { routes: RouteView[] }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const formId = useId()
  const rulesId = useId()
  const [url, setUrl] = useState('')
  const [name, setName] = useState('')
  const [rules, setRules] = useState<string[]>([])
  const [draft, setDraft] = useState('')
  // 打了沒按「加入規則」的那一條也算：Mikan 加入後很快就送單，漏掉它就擋不到了。
  const typed = draft.trim()
  const sentRules = typed === '' || rules.includes(typed) ? rules : [...rules, typed]
  // `undefined` 是那一格還沒動過：用預填（只有一條時就是它）。Route 清單晚到時預填跟著到。
  const [picked, setPicked] = useState<Partial<KindRoutes>>({})
  const defaults = prefilled(routes)
  const chosen: KindRoutes = { tv: picked.tv ?? defaults.tv, movie: picked.movie ?? defaults.movie }
  const add = useMutation({
    mutationFn: () => addFeed(url.trim(), name.trim(), chosen, sentRules),
    onSuccess: async () => {
      setUrl('')
      setName('')
      setRules([])
      setDraft('')
      setPicked({})
      await queryClient.invalidateQueries({ queryKey: RSS_KEY })
    },
  })
  const refusal = add.isError ? parseRssRefusal(add.error) : null
  // 寫壞的規則說在規則欄下，其他的說在網址欄下。
  const rulesRefused = refusal?.reason === 'rule_invalid'
  const ready = url.trim() !== '' && complete(chosen, routes)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (ready) add.mutate()
  }

  return (
    <div className="grid gap-3 border-2 border-rule bg-well px-4 py-3">
      <form id={formId} onSubmit={submit} className="grid gap-3">
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
          error={add.isError && !rulesRefused ? rssProblem(t, add.error) : undefined}
          onChange={(event) => setUrl(event.target.value)}
        />
        <Field
          label={t('rss.feeds.name')}
          hint={t('rss.feeds.nameHint')}
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        <KindRoutePickers
          routes={routes}
          value={chosen}
          onChange={(kind, route) => setPicked((now) => ({ ...now, [kind]: route }))}
        />
      </form>
      {/* `group` 不是 `region`：頁上已有一段叫「排除條件」的全域那一層。 */}
      <div role="group" aria-labelledby={rulesId} className="grid gap-2">
        <p id={rulesId} className="label text-ink-dim">
          {t('rss.rules.title')}
        </p>
        <RulesFields
          rules={rules}
          draft={draft}
          setDraft={setDraft}
          lede={t('rss.rules.addLede')}
          // 送出中不改：送出的是按下那一刻的那一組，成功之後表單清空。
          busy={add.isPending}
          error={rulesRefused ? rssProblem(t, add.error) : undefined}
          commit={(next, done) => {
            setRules(next)
            done()
          }}
        />
      </div>
      <div className="sm:max-w-xs">
        <PrimaryButton form={formId} type="submit" busy={add.isPending} disabled={!ready}>
          {add.isPending ? t('rss.feeds.adding') : t('rss.feeds.addAction')}
        </PrimaryButton>
      </div>
    </div>
  )
}

/** 那一列不在畫面內時捲到它（在畫面內就不動，免得每按一次都跳一下）。 */
function bringBack(element: HTMLElement | null) {
  if (!element) return
  const box = element.getBoundingClientRect()
  if (box.top < 0 || box.bottom > window.innerHeight) element.scrollIntoView({ block: 'nearest' })
}

/**
 * 自動綁定送進的 Route，劇集、電影各一格（M4 票 105，照 Sonarr Import List 的 Root Folder 必填）。
 * 那一種有啟用中的 Route 才有那一格；沒有「不指定」：還沒選時是一個選不到的提示，表單送不出去。
 * 只列啟用中的：停用的那一條自動綁定本來就不看。
 */
function KindRoutePickers({
  routes,
  value,
  onChange,
  kinds = KINDS,
}: {
  routes: RouteView[]
  value: KindRoutes
  onChange: (kind: MediaKind, route: number) => void
  /** 這個 Feed 用得到的那幾種（`Feed.route_kinds`）；新 Feed 兩種都用得到。 */
  kinds?: readonly MediaKind[]
}) {
  return (
    <>
      {kinds.map((kind) => (
        <KindRoutePicker
          key={kind}
          kind={kind}
          choices={routesFor(routes, kind)}
          value={value[kind]}
          onChange={(route) => onChange(kind, route)}
        />
      ))}
    </>
  )
}

function KindRoutePicker({
  kind,
  choices,
  value,
  onChange,
}: {
  kind: MediaKind
  choices: RouteView[]
  value: number | null
  onChange: (route: number) => void
}) {
  const { t } = useTranslation()
  const id = useId()
  if (choices.length === 0) return null

  return (
    <p className="grid gap-2">
      <label htmlFor={id} className="label text-ink-dim">
        {t(`rss.feeds.routeFor.${kind}`)}
      </label>
      <select
        id={id}
        required
        aria-describedby={`${id}-hint`}
        value={value ?? ''}
        onChange={(event) => onChange(Number(event.target.value))}
        className="value w-full border-2 border-rule-strong bg-hull px-3 py-2.5 text-sm text-ink focus:border-ink"
      >
        {value === null && (
          <option value="" disabled>
            {t('rss.feeds.routePick')}
          </option>
        )}
        {choices.map((row) => (
          <option key={row.id} value={row.id}>
            {row.name}
          </option>
        ))}
      </select>
      <span id={`${id}-hint`} className="text-xs text-ink-dim">
        {t(`rss.feeds.routeHint.${kind}`)}
      </span>
    </p>
  )
}

/**
 * 「改 Route」（M4 票 105）：就地展開，不是 dialog（同 `SeriesBinder` 的確認區）。確認區說出存下之後
 * 會當場綁上幾部——這個 Feed 長出、因為 Route 不只一條而停在待綁定的（`awaiting_route`）。
 */
function FeedRoutes({
  feed,
  routes,
  onSaved,
}: {
  feed: Feed
  routes: RouteView[]
  /** 結果句在這一列的狀態句裡（與輪詢的同一個 live region）：存下之後確認區收起，那一句留著。 */
  onSaved: (outcome: FeedRoutesOutcome | null) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const ledeId = useId()
  const [picked, setPicked] = useState<Partial<KindRoutes>>({})
  const own = routesOf(feed, routes)
  const defaults = prefilled(routes)
  const chosen: KindRoutes = {
    tv: picked.tv ?? own.tv ?? defaults.tv,
    movie: picked.movie ?? own.movie ?? defaults.movie,
  }
  const binds = bindsNow(feed, routes)
  const save = useMutation({
    mutationFn: () => setFeedRoutes(feed.id, chosen),
    onMutate: () => onSaved(null),
    onSuccess: async (outcome) => {
      onSaved(outcome)
      setPicked({})
      close()
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: RSS_KEY }),
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
      ])
    },
  })
  const refusal = save.isError ? parseRssRefusal(save.error) : null

  return (
    <>
      {asked ? (
        <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={ledeId}>
          <p id={ledeId} className="max-w-prose text-xs text-ink">
            {t('rss.feeds.routesLede')}
          </p>
          <KindRoutePickers
            routes={routes}
            value={chosen}
            kinds={feed.route_kinds}
            onChange={(kind, route) => setPicked((now) => ({ ...now, [kind]: route }))}
          />
          {binds > 0 && (
            <p className="max-w-prose text-xs text-ink">
              {t('rss.feeds.routesBinds', { count: binds })}
            </p>
          )}
          <div className={CONFIRM_ACTIONS}>
            <PrimaryButton
              type="button"
              busy={save.isPending}
              disabled={!complete(chosen, routes, feed.route_kinds)}
              onClick={() => save.mutate()}
            >
              {save.isPending
                ? t('rss.feeds.routesSaving')
                : binds > 0
                  ? t('rss.feeds.routesSaveBind', { count: binds })
                  : t('rss.feeds.routesSave')}
            </PrimaryButton>
            <GhostButton type="button" onClick={close}>
              {t('common.cancel')}
            </GhostButton>
          </div>
          {save.isError &&
            (refusal ? (
              <Notice signal="blocked" label={t('common.failed')}>
                {t(`rss.refusal.${refusal.reason}`)}
                {refusal.detail ? (
                  <span className="value block text-xs">{refusal.detail}</span>
                ) : null}
              </Notice>
            ) : (
              <RequestFailed error={save.error} lead={t('request.notDone')} />
            ))}
        </ConfirmPanel>
      ) : (
        <div>
          <GhostButton ref={trigger} type="button" onClick={open}>
            {t('rss.feeds.changeRoutes')}
          </GhostButton>
        </div>
      )}
    </>
  )
}

function FeedRow({ feed, routes }: { feed: Feed; routes: RouteView[] }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const headingId = useId()
  // 一列一個狀態句：最近一次輪詢、或最近一次改 Route 的結果，後做的那一件蓋掉前一件。
  const [polled, setPolled] = useState<PollOutcome | null>(null)
  const [saved, setSaved] = useState<FeedRoutesOutcome | null>(null)
  const self = useRef<HTMLElement>(null)
  const refresh = () => queryClient.invalidateQueries({ queryKey: RSS_KEY })
  const poll = useMutation({
    mutationFn: () => pollFeed(feed.id),
    onMutate: () => {
      setPolled(null)
      setSaved(null)
    },
    onSuccess: async (outcome) => {
      setPolled(outcome)
      await Promise.all([refresh(), queryClient.invalidateQueries({ queryKey: ['jobs'] })])
      // 需要人的那幾段浮在頁首（第一輪、待綁定），這一輪長出來的會把這一列連同結果句推出畫面
      // （M3 票 21 的 audit：390px 上從 y 356 推到 2443）。重畫之後捲回來。
      requestAnimationFrame(() => bringBack(self.current))
    },
  })
  const remove = useMutation({ mutationFn: () => deleteFeed(feed.id), onSuccess: refresh })
  const own = routesOf(feed, routes)
  const named = feed.route_kinds.flatMap((kind) => {
    const name = routes.find((row) => row.id === own[kind])?.name
    return name === undefined ? [] : [{ kind, name }]
  })
  const unset = unsetKinds(feed, routes)

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
        {named.map(({ kind, name }) => (
          <span key={kind}>
            {' '}
            <Dot /> {t(`rss.feeds.routeFor.${kind}`)} <span className="value">{name}</span>
          </span>
        ))}
      </p>
      {/* 票 105 之前加的 Feed：那一種有 Route，這一格卻空著——認出來的作品會停在待綁定。 */}
      {unset.map((kind) => (
        <Notice key={kind} signal="assigned" label={t('rss.feeds.routeUnset')}>
          {t(`rss.feeds.routeUnsetWhy.${kind}`)}
        </Notice>
      ))}
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
        {saved &&
          (saved.bound > 0
            ? t('rss.feeds.routesSavedBound', { count: saved.bound, sent: saved.submitted })
            : t('rss.feeds.routesSaved'))}
      </p>
      {(poll.isError || remove.isError) && (
        <RequestFailed error={poll.error ?? remove.error} lead={t('request.notDone')} />
      )}
      <FeedRoutes
        feed={feed}
        routes={routes}
        onSaved={(outcome) => {
          setPolled(null)
          setSaved(outcome)
        }}
      />
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
