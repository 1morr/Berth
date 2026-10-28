import { useId, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'

import type { Media } from '../api/media'
import {
  bangumiQueryOptions,
  bangumiSearchQueryOptions,
  RSS_KEY,
  subscribeMikan,
  subscribeSearch,
  workSeriesQueryOptions,
  type BangumiHit,
  type Feed,
  type RssSeries,
  type Subgroup,
} from '../api/rss'
import type { Schemas } from '../api/schemas'
import { queriesQueryOptions } from '../api/search'
import { ConfirmPanel } from '../components/ConfirmPanel'
import {
  CONFIRM_ACTIONS,
  Field,
  GhostButton,
  PrimaryButton,
  TEXT_LINK,
} from '../components/controls'
import { Dot } from '../components/Dot'
import { RequestFailed } from '../components/RequestFailed'
import { SectionHeading } from '../components/SectionHeading'
import { SIGNAL_FILL } from '../components/signal'
import { Timestamp } from '../components/Timestamp'
import { useInPlaceConfirm } from '../components/useInPlaceConfirm'
import { displayRound } from '../i18n/displayRound'
import { firstBatchAskText } from '../rss/firstBatchAsk'
import { groupName } from '../rss/seriesByWork'
import { FirstRound } from '../rss/FirstRoundSection'
import { preselect } from '../rss/preselect'
import { ExistingDownload, type ExistingTarget } from './ExistingDownload'
import { excludedText, sentences } from './excludedText'
import { RssRefusalNotice } from '../rss/RssRefusalNotice'
import { RoutePicker } from './RoutePicker'

type FeedKind = Schemas['FeedKind']
const SOURCES: readonly FeedKind[] = ['mikan', 'nyaa', 'acgrip']

/** 這一段在作品頁上的錨點。 */
export const SUBSCRIBE_ANCHOR = 'media-subscribe'

/**
 * 詳情頁的「RSS 訂閱」（M3 票 19、`.scratch/m3/subscribe-shape.md`、brief §15「從 Media 頁訂閱」）。
 *
 * 次要入口：主要的仍是 `/rss` 貼 Mikan 聚合 feed。這一段做兩件事：列出已經綁在這部作品上的 RSS Series，
 * 以及就地展開的「新增訂閱」——選一個來源建一條 feed，並**預先綁定這部作品**：
 *
 * - **Mikan**：Berth 代搜番組（2026-09-26 拍板；搜尋框預填原文標題，Mikan 的番組名來自 bgm.tv，日文原名
 *   最穩）→ 選字幕組 → 訂閱。它的單一 feed 當場讀完，整季補齊（同綁定的補舊集，一律補）。
 *   選好字幕組之後也可以不訂閱、「只下載現有的」（M4 票 112）：已完結、字幕組只出合集的作品，訂閱建的
 *   Feed 擋下合集、之後也不會再有新的；訂閱之後有被擋下的，回報那一句也指向它。
 * - **Nyaa / acg.rip**：以這部作品的標題（與搜尋區塊同一份）建搜尋 feed，它長出的 RSS Series 都綁到這部作品
 *   （2026-09-26 拍板）。第一輪照樣等人選，建好之後就地畫 `/rss` 那一塊第一輪預覽。
 *
 * 只有 admin 畫這一段（呼叫端判斷）：`/rss/*` 整組 admin，後端同時回 403。
 */
export function SubscribePanel({ media }: { media: Media }) {
  const { t } = useTranslation()
  const headingId = useId()
  const series = useQuery(workSeriesQueryOptions(media.id))
  const [said, setSaid] = useState<Said>({ text: '', existing: null })

  return (
    // 固定的 id：搜尋區在沒有接索引站時連過來（`IndexerNotice`，M4 票 61）。
    <section id={SUBSCRIBE_ANCHOR} className="grid gap-4" aria-labelledby={headingId}>
      <SectionHeading
        id={headingId}
        label={t('rss.subscribe.title')}
        extra={
          <Link to="/rss" className={`${TEXT_LINK} ms-auto`}>
            {t('rss.subscribe.toRss')}
          </Link>
        }
      />

      {series.isError ? (
        <RequestFailed error={series.error} lead={t('rss.readFailed')} />
      ) : series.data && series.data.length > 0 ? (
        <ul className="grid gap-px border-2 border-rule bg-rule">
          {series.data.map((row) => (
            <SeriesLine key={row.id} row={row} />
          ))}
        </ul>
      ) : (
        series.data && <p className="max-w-prose text-sm text-ink-dim">{t('rss.subscribe.none')}</p>
      )}

      <Subscriber media={media} onDone={setSaid} />
      {/* 看得見的一句（訂閱之後表單收起，列表多一列；送出幾集只在這裡說），也念給螢幕閱讀器。 */}
      <p aria-live="polite" className="max-w-prose text-sm text-ink empty:hidden">
        {said.text}
      </p>
      {said.existing && (
        // 換一條網址（再訂閱另一組）就是另一份清單。
        <ExistingDownload key={said.existing.url} media={media} target={said.existing} />
      )}
    </section>
  )
}

/** 訂閱之後的那一句；有被排除條件擋下的時候帶著「只下載現有的」要讀的那一條。 */
interface Said {
  text: string
  existing: ExistingTarget | null
}

type OnDone = (said: Said) => void

/**
 * 一個綁在這部作品上的 RSS Series：來源、字幕組、第一批確認了沒、最近一集。第一批還在等人時，標籤下面說它在問
 * 什麼（與審核頁那一組同一句，M4 票 11）。
 */
function SeriesLine({ row }: { row: RssSeries }) {
  const { t, i18n } = useTranslation()
  const title = displayRound(i18n.language, { 'zh-Hant': row.media_title, en: row.media_title_en })

  return (
    <li className="grid min-w-0 gap-1 bg-hull px-3 py-2">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
        {row.source && (
          <span className="label bg-deck px-1.5 py-0.5 text-ink">
            {t(`rss.kind.${row.source}`)}
          </span>
        )}
        <span className="value min-w-0 text-sm wrap-anywhere text-ink">
          {groupName(row) || row.title_raw}
        </span>
        {/* 還沒確認是一件在等人的事（`assigned`）；確認過是常態，不塗漆（The Usual Stays Unpainted Rule）。 */}
        {row.confirmed ? (
          <span className="text-xs text-ink-dim">{t('rss.subscribe.confirmed')}</span>
        ) : (
          <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.assigned}`}>
            {t('rss.subscribe.firstBatch')}
          </span>
        )}
      </p>
      {!row.confirmed && row.ask && (
        <p className="max-w-prose text-xs text-ink">
          {firstBatchAskText(t, { title, group: groupName(row), ask: row.ask })}
        </p>
      )}
      {row.latest_title ? (
        <p className="text-xs text-ink-dim">
          {t('rss.subscribe.latest')}{' '}
          <span className="value wrap-anywhere text-ink">{row.latest_title}</span> <Dot />{' '}
          <Timestamp at={row.latest_at} />
        </p>
      ) : (
        <p className="text-xs text-ink-dim">{t('rss.subscribe.nothingYet')}</p>
      )}
    </li>
  )
}

/** 「新增訂閱」：就地展開的確認區塊（同 `SeriesBinder`），不是 dialog。 */
function Subscriber({ media, onDone }: { media: Media; onDone: OnDone }) {
  const { t } = useTranslation()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const headingId = useId()
  const [source, setSource] = useState<FeedKind>('mikan')
  // `undefined` 是「還沒選過」：那時用預選；選了「不選」是 `null`（同 `SeriesBinder`）。
  const [chosen, setChosen] = useState<number | null | undefined>(undefined)
  const route = chosen === undefined ? preselect(media) : chosen
  // 建好的搜尋 feed：這一塊換成它的第一輪預覽。
  const [made, setMade] = useState<Feed | null>(null)

  const finish: OnDone = (said) => {
    onDone(said)
    setMade(null)
    close()
  }

  if (!asked) {
    return (
      <div>
        <GhostButton ref={trigger} type="button" onClick={open}>
          {t('rss.subscribe.start')}
        </GhostButton>
      </div>
    )
  }

  if (made !== null) {
    return (
      <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={headingId}>
        <p id={headingId} className="max-w-prose text-sm text-ink">
          {t('rss.subscribe.made', { name: made.name })}
        </p>
        <FirstRound feed={made} onDone={(text) => finish({ text, existing: null })} />
        <div className={CONFIRM_ACTIONS}>
          <span />
          <GhostButton
            type="button"
            onClick={() => finish({ text: t('rss.subscribe.later'), existing: null })}
          >
            {t('rss.subscribe.decideLater')}
          </GhostButton>
        </div>
      </ConfirmPanel>
    )
  }

  return (
    <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={headingId}>
      <p id={headingId} className="label text-ink-dim">
        {t('rss.subscribe.label')}
      </p>
      <Options
        label={t('rss.subscribe.source')}
        items={SOURCES}
        keyOf={(kind) => kind}
        picked={source}
        onPick={setSource}
        render={(kind) => (
          <>
            <span className="label">{t(`rss.kind.${kind}`)}</span>
            <span className="text-xs text-ink-dim">{t(`rss.subscribe.about.${kind}`)}</span>
          </>
        )}
      />
      <RoutePicker media={media} value={route} onChange={setChosen} />
      {source === 'mikan' ? (
        <MikanPicker media={media} route={route} onDone={finish} onCancel={close} />
      ) : (
        <SearchFeedPicker
          // 換站時搜尋詞與錯誤都重來。
          key={source}
          kind={source}
          media={media}
          route={route}
          onMade={setMade}
          onCancel={close}
        />
      )}
    </ConfirmPanel>
  )
}

/** Mikan：搜番組 → 選字幕組 → 補不補舊集 → 訂閱。 */
function MikanPicker({
  media,
  route,
  onDone,
  onCancel,
}: {
  media: Media
  route: number | null
  onDone: OnDone
  onCancel: () => void
}) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const initial = media.title_original || media.title_en || media.title
  const [term, setTerm] = useState(initial)
  // 送出去的那一個詞：打字不搜，按了才搜（Mikan 的搜尋頁一次上 MB）。
  const [searched, setSearched] = useState(initial.trim())
  const [bangumi, setBangumi] = useState<BangumiHit | null>(null)
  const [group, setGroup] = useState<Subgroup | null>(null)
  const hits = useQuery({ ...bangumiSearchQueryOptions(searched), enabled: searched !== '' })
  const detail = useQuery({ ...bangumiQueryOptions(bangumi?.id ?? 0), enabled: bangumi !== null })
  const subscribe = useMutation({
    mutationFn: async () => {
      if (bangumi === null || group === null || route === null) throw new Error('nothing picked')
      // 「只下載現有的」要讀的那一條，記下按下那一刻的那一組（不讀之後才變的 state）。
      const target: ExistingTarget = { url: group.feed_url, route }
      const done = await subscribeMikan({
        media: media.id,
        route,
        bangumi: bangumi.id,
        subgroup: group.id,
        name: `${bangumi.title} · ${group.name}`,
        // 挑的時候讀過的字幕組名：RSS 頁的來源那一格說它，不說 id（M4 票 13）。番組名單一 feed 自己帶。
        subgroup_name: group.name,
      })
      return { done, target }
    },
    onSuccess: async ({ done, target }) => {
      const excluded = excludedText(t, done.excluded, i18n.language)
      onDone({
        text: sentences(
          [t('rss.subscribe.subscribed', { count: done.series.submitted }), excluded],
          i18n.language,
        ),
        // 有被擋下的：回報指向「只下載現有的」，讀的是按下訂閱那一刻的那一組。
        existing: excluded ? target : null,
      })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: RSS_KEY }),
        queryClient.invalidateQueries({ queryKey: ['mikan'] }),
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
        // 資料夾名定了、這部作品變成 tracked（同綁定）。
        queryClient.invalidateQueries({ queryKey: ['media'] }),
      ])
    },
  })

  const pickBangumi = (hit: BangumiHit) => {
    setBangumi(hit)
    setGroup(null)
  }

  return (
    <>
      <form
        className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end"
        onSubmit={(event) => {
          event.preventDefault()
          setSearched(term.trim())
          setBangumi(null)
          setGroup(null)
        }}
      >
        <Field
          label={t('rss.subscribe.mikanSearch')}
          type="search"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
        />
        <GhostButton type="submit" busy={hits.isFetching}>
          {hits.isFetching ? t('rss.subscribe.searching') : t('rss.subscribe.search')}
        </GhostButton>
      </form>

      {hits.isError ? (
        <Refusal error={hits.error} />
      ) : hits.data && hits.data.length === 0 ? (
        <p className="max-w-prose text-xs text-ink-dim">{t('rss.subscribe.noBangumi')}</p>
      ) : (
        hits.data && (
          <Options
            label={t('rss.subscribe.bangumi')}
            items={hits.data}
            keyOf={(hit) => String(hit.id)}
            picked={bangumi}
            onPick={pickBangumi}
            render={(hit) => <span className="value wrap-anywhere">{hit.title}</span>}
          />
        )
      )}

      {bangumi !== null && detail.isPending && (
        <p className="text-xs text-ink-dim">{t('rss.subscribe.reading')}</p>
      )}
      {detail.isError && <Refusal error={detail.error} />}
      {detail.data &&
        (detail.data.subgroups.length === 0 ? (
          <p className="max-w-prose text-xs text-ink-dim">{t('rss.subscribe.noSubgroups')}</p>
        ) : (
          <Options
            label={t('rss.subscribe.subgroup')}
            items={detail.data.subgroups}
            keyOf={(one) => String(one.id)}
            picked={group}
            onPick={setGroup}
            locked={(one) =>
              one.bound_to === null
                ? null
                : one.bound_to === media.id
                  ? t('rss.subscribe.boundHere')
                  : t('rss.subscribe.boundElsewhere', { id: one.bound_to })
            }
            render={(one) => <SubgroupLine group={one} />}
          />
        ))}

      {group !== null && (
        <>
          <FolderLine media={media} />
          <p className="max-w-prose text-xs text-ink-dim">{t('rss.subscribe.season')}</p>
        </>
      )}
      {group !== null && route !== null && (
        // 換字幕組就是另一份清單，收起來從頭來。
        <ExistingDownload
          key={group.feed_url}
          media={media}
          target={{ url: group.feed_url, route }}
        />
      )}

      <div className={CONFIRM_ACTIONS}>
        {group !== null && route !== null ? (
          <PrimaryButton
            type="button"
            busy={subscribe.isPending}
            onClick={() => subscribe.mutate()}
          >
            {subscribe.isPending ? t('rss.subscribe.subscribing') : t('rss.subscribe.confirm')}
          </PrimaryButton>
        ) : (
          <span />
        )}
        <GhostButton type="button" onClick={onCancel}>
          {t('common.cancel')}
        </GhostButton>
      </div>
      {subscribe.isError && <Refusal error={subscribe.error} />}
    </>
  )
}

/**
 * 字幕組那一顆鍵的內容：名字、幾筆、最近更新，最新一筆的發佈名（看得出語言與解析度）。
 * 確認卡選字幕組也用它（M5 票 26），所以只要這四格。
 */
export function SubgroupLine({
  group,
}: {
  group: Pick<Subgroup, 'name' | 'releases' | 'updated' | 'latest'>
}) {
  const { t, i18n } = useTranslation()
  const updated = group.updated
    ? new Date(`${group.updated}T00:00:00`).toLocaleDateString(i18n.language)
    : '—'

  return (
    <span className="grid min-w-0 gap-0.5">
      <span className="flex flex-wrap items-baseline gap-x-2">
        <span className="value wrap-anywhere">{group.name}</span>
        <span className="text-xs text-ink-dim">
          {t('rss.subscribe.releases', { count: group.releases, updated })}
        </span>
      </span>
      {group.latest && (
        <span className="value text-xs wrap-anywhere text-ink-dim">{group.latest}</span>
      )}
    </span>
  )
}

/** Nyaa / acg.rip：作品的標題集合一個一顆鍵，下面一格可改的搜尋詞。 */
function SearchFeedPicker({
  kind,
  media,
  route,
  onMade,
  onCancel,
}: {
  kind: FeedKind
  media: Media
  route: number | null
  onMade: (feed: Feed) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  // 與搜尋區塊同一份名字（後端算）：英文名、原名、中文名、簡體中文名，不含三十幾個別名，也不含季記號——
  // 訂閱的是一個搜尋詞，`第3季` 那幾個是一次搜尋的查詢，不是名字（M4 票 84）。
  const planned = useQuery(queriesQueryOptions(media.id))
  const titles = (planned.data?.names ?? [])
    .filter((chip) => !chip.kinds.includes('alias'))
    .map((chip) => chip.name)
  // `null` 是還沒動過：用標題集合的第一個。
  const [typed, setTyped] = useState<string | null>(null)
  const term = typed ?? titles[0] ?? media.title_en
  const create = useMutation({
    mutationFn: () => {
      if (route === null) throw new Error('no route')
      return subscribeSearch({ media: media.id, route, kind, term: term.trim() })
    },
    onSuccess: async (feed) => {
      onMade(feed)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: RSS_KEY }),
        queryClient.invalidateQueries({ queryKey: ['media'] }),
      ])
    },
  })

  return (
    <>
      {titles.length > 0 && (
        <Options
          label={t('rss.subscribe.titles')}
          items={titles}
          keyOf={(title) => title}
          picked={term}
          onPick={setTyped}
          render={(title) => <span className="value wrap-anywhere">{title}</span>}
        />
      )}
      <Field
        label={t('rss.subscribe.term')}
        hint={t(`rss.subscribe.termHint.${kind}`)}
        value={term}
        onChange={(event) => setTyped(event.target.value)}
      />
      <FolderLine media={media} />
      <div className={CONFIRM_ACTIONS}>
        {route !== null && term.trim() !== '' ? (
          <PrimaryButton type="button" busy={create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? t('rss.subscribe.creating') : t('rss.subscribe.create')}
          </PrimaryButton>
        ) : (
          <span />
        )}
        <GhostButton type="button" onClick={onCancel}>
          {t('common.cancel')}
        </GhostButton>
      </div>
      {create.isError && <Refusal error={create.error} />}
    </>
  )
}

/**
 * 資料夾名在綁定那一刻定死（plan §2.2），之後的送單沒有人按，所以按下去之前重述那一串（同 `SeriesBinder`）。
 */
function FolderLine({ media }: { media: Media }) {
  const { t } = useTranslation()

  return (
    <div className="grid gap-1">
      <p className="max-w-prose text-xs text-ink">
        {media.folder_frozen ? t('rss.bind.alreadyFrozen') : t('rss.bind.willFreeze')}
      </p>
      <p className="value text-xs wrap-anywhere text-ink">{media.folder_name || '—'}</p>
    </div>
  )
}

/**
 * 一串選項，一個一顆鍵，選定的是按下的樣子（同 `rss/WorkChoices.tsx` 的 `Choices`；DESIGN.md「先選再確認」）。
 * 確認卡選字幕組也用它（M5 票 26）。
 */
export function Options<T>({
  label,
  items,
  keyOf,
  picked,
  onPick,
  render,
  locked = () => null,
}: {
  label: string
  items: readonly T[]
  keyOf: (item: T) => string
  picked: T | null
  onPick: (item: T) => void
  render: (item: T) => ReactNode
  /** 選不得時說為什麼（例如那個字幕組已經綁了）；選得了是 `null`。 */
  locked?: (item: T) => string | null
}) {
  const labelId = useId()
  const pickedKey = picked === null ? null : keyOf(picked)

  return (
    <div className="grid gap-1">
      <p id={labelId} className="label text-ink-dim">
        {label}
      </p>
      <ul className="grid gap-1" aria-labelledby={labelId}>
        {items.map((item) => {
          const why = locked(item)
          const on = pickedKey === keyOf(item)
          return (
            <li key={keyOf(item)}>
              <button
                type="button"
                aria-pressed={on}
                disabled={why !== null}
                onClick={() => onPick(item)}
                className={`flex min-h-6 w-full flex-wrap items-baseline gap-x-2 gap-y-1 border-2 px-3 py-2 text-left text-sm text-ink disabled:cursor-not-allowed disabled:text-ink-dim ${
                  on ? 'border-rule-strong bg-deck' : 'border-rule hover:border-rule-strong'
                }`}
              >
                {render(item)}
                {why !== null && <span className="text-xs">{why}</span>}
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function Refusal({ error }: { error: unknown }) {
  const { t } = useTranslation()
  return <RssRefusalNotice error={error} unreachable={t('rss.subscribe.unreachable')} />
}
