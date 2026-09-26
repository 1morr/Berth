import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { MIN_QUERY_LENGTH, searchQueryOptions } from '../api/discover'
import { refusalOf, submitJob } from '../api/jobs'
import { mediaQueryOptions, type Media } from '../api/media'
import {
  ONESHOT_KEY,
  oneshotQueryOptions,
  parseRssRefusal,
  type Oneshot,
  type OneshotItem,
} from '../api/rss'
import { Field, GhostButton, Notice, PrimaryButton, STICKY_ACTION } from '../components/controls'
import { Dot } from '../components/Dot'
import { SIGNAL_FILL } from '../components/signal'
import { SEARCH_DEBOUNCE_MS, useDebounced } from '../components/useDebounced'
import { whenText } from '../components/queueText'
import { displayRound } from '../i18n/displayRound'
import { JobLink } from '../jobs/JobLink'
import { RoutePicker } from '../media/RoutePicker'
import { estimate, formatSize, tagTokens } from '../media/searchResult'
import { freshSingles, sendOrder, tally, type Outcome } from './oneshotBatch'
import { searchTerm } from './searchTerm'
import { SectionHeading } from './SectionHeading'
import { preselect } from './preselect'
import { Choices, type Pickable } from './WorkChoices'

/**
 * 一次性 RSS 連結（brief §15、M3 票 18）：貼一條網址 → 讀一次 → 挑作品與 Route → 勾幾筆 → 送出。
 *
 * **不建 Feed**：讀是 `POST /rss/oneshot`（只讀），送是逐筆的一般送單 `POST /jobs`（`trigger = manual`，
 * 與搜尋結果表同一支）。一次勾的同一批共用一部作品與一條 Route。
 *
 * **作品排在清單前面**：選了之後清單換成照那部作品換算的季集，並標出帳本已經有的那幾筆——勾之前就
 * 看得到哪幾集不必再下。資料夾名在第一次送單那一刻定下來，所以它印在送出鍵的上方（同 `SubmitAction`）。
 *
 * **排除條件不擋**（它們只管自動下載）：合集、區間標出來，照樣勾得了；「勾選全部單集」不勾它們。
 *
 * 送出是**逐筆、舊的先**：一筆被拒不擋下一筆（那一列就地說理由）；不是「後端說不行」的失敗（網路斷了、
 * 401）就停下來，沒送的留著勾。區塊送完不會消失，結果那一句是區塊裡的 `role="status"`，不經頁面的
 * `aria-live`（那一條給會離開畫面的列）。
 */
export function OneshotSection() {
  const { t } = useTranslation()
  const headingId = useId()
  const [draft, setDraft] = useState('')
  const [url, setUrl] = useState<string | null>(null)
  const [work, setWork] = useState<Pickable | null>(null)
  // `undefined` 是「還沒選過」：那時用預選（`preselect`）；選了「不選」是 `null`（同 `SeriesBinder`）。
  const [chosen, setChosen] = useState<number | null | undefined>(undefined)
  const detail = useQuery({ ...mediaQueryOptions(work?.id ?? ''), enabled: work !== null })
  const media = work !== null ? detail.data : undefined
  const route = chosen === undefined ? preselect(media) : chosen
  const read = useQuery({
    ...oneshotQueryOptions(url ?? '', media?.id ?? null, media ? route : null),
    enabled: url !== null,
    // 同一條網址換了作品或 Route 時，重讀的那幾秒清單不消失（換成換算過的季集而已）；換了網址就是
    // 另一批，不拿舊的那一份墊著——不然讀取中勾得到上一個 feed 的項目。
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === url ? previous : undefined,
  })

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const next = draft.trim()
    if (next === '') return
    // 同一條網址再按一次是「重讀」：key 沒變，要自己叫它（讀不到之後，句子叫人再按一次）。
    if (next === url) {
      void read.refetch()
      return
    }
    setUrl(next)
    setWork(null)
    setChosen(undefined)
  }
  const refusal = read.isError ? parseRssRefusal(read.error) : null
  const failure = refusal
    ? refusal.reason === 'feed_unreachable'
      ? t('rss.oneshot.unreachable')
      : t(`rss.refusal.${refusal.reason}`)
    : read.isError
      ? t('rss.failed')
      : undefined

  return (
    <section aria-labelledby={headingId} className="grid gap-3">
      <SectionHeading id={headingId} label={t('rss.oneshot.title')} />
      <p className="max-w-prose text-sm text-ink-dim">{t('rss.oneshot.lede')}</p>
      <form onSubmit={submit} className="grid gap-3 border-2 border-rule bg-well px-4 py-3">
        <Field
          label={t('rss.oneshot.url')}
          hint={t('rss.oneshot.urlHint')}
          type="url"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          required
          value={draft}
          error={failure}
          onChange={(event) => setDraft(event.target.value)}
        />
        {/* 上游回的原文（英文），不翻譯（與精靈的纜繩同一個規矩）。 */}
        {refusal?.detail && refusal.reason !== 'feed_unsupported' && (
          <p className="value text-xs wrap-anywhere text-ink-dim">{refusal.detail}</p>
        )}
        <div className="sm:max-w-xs">
          <PrimaryButton type="submit" busy={read.isFetching} disabled={draft.trim() === ''}>
            {read.isFetching ? t('rss.oneshot.reading') : t('rss.oneshot.read')}
          </PrimaryButton>
        </div>
      </form>
      {/* 重讀失敗時（換作品、送單之後）清單與勾選留著，失敗說在欄位下。 */}
      {read.data && url !== null && (
        <Listing
          // 換一條網址就是另一批：勾選與結果從頭來。
          key={url}
          read={read.data}
          work={work}
          onWork={(next) => {
            setWork(next)
            setChosen(undefined)
          }}
          media={media}
          mediaFailed={work !== null && detail.isError}
          route={route}
          onRoute={setChosen}
        />
      )}
    </section>
  )
}

function Listing({
  read,
  work,
  onWork,
  media,
  mediaFailed,
  route,
  onRoute,
}: {
  read: Oneshot
  work: Pickable | null
  onWork: (work: Pickable) => void
  media: Media | undefined
  mediaFailed: boolean
  route: number | null
  onRoute: (route: number | null) => void
}) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const listId = useId()
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set())
  const [outcomes, setOutcomes] = useState<ReadonlyMap<string, Outcome>>(new Map())
  const [progress, setProgress] = useState(0)
  const items = read.items
  const all = freshSingles(items)
  const allPicked = all.size > 0 && [...all].every((guid) => picked.has(guid))

  const send = useMutation({
    mutationFn: async () => {
      if (!media || route === null) throw new Error('nothing picked')
      const order = sendOrder(items, picked)
      // 這一批的結果另外記一份：`onSuccess` 裡讀 state 拿到的是按下那一刻的。
      const settled = new Map<string, Outcome>()
      setProgress(0)
      for (const row of order) {
        let outcome: Outcome
        try {
          const created = await submitJob({
            source: {
              url: row.url,
              title: row.title,
              info_hash: row.info_hash,
              published_at: row.published_at,
              size: row.size,
            },
            media: media.id,
            route,
          })
          outcome = { kind: created.created ? 'sent' : 'already', hash: created.job.hash }
        } catch (error) {
          const refused = refusalOf(error)
          // 不是後端說不行（網路斷了、登入過期）：停下來，沒送的留著勾。
          if (refused === null) throw error
          outcome = { kind: 'refused', reason: refused.reason, detail: refused.detail }
        }
        settled.set(row.guid, outcome)
        setOutcomes((before) => new Map(before).set(row.guid, outcome))
        if (outcome.kind !== 'refused') {
          setPicked((before) => {
            const next = new Set(before)
            next.delete(row.guid)
            return next
          })
        }
        setProgress((done) => done + 1)
      }
      return tally(settled)
    },
    onSettled: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
        // 送單之後這部作品變成 tracked、資料夾名也定了（同 `SubmitAction`）。
        queryClient.invalidateQueries({ queryKey: ['media'] }),
        // 重讀一次：哪幾筆已經有下載了。
        queryClient.invalidateQueries({ queryKey: ONESHOT_KEY }),
      ])
    },
  })

  const toggle = (guid: string, on: boolean) =>
    setPicked((before) => {
      const next = new Set(before)
      if (on) next.add(guid)
      else next.delete(guid)
      return next
    })

  if (items.length === 0) {
    return <p className="max-w-prose text-sm text-ink-dim">{t('rss.oneshot.empty')}</p>
  }

  const order = sendOrder(items, picked)
  return (
    <div className="grid gap-3">
      <p className="text-xs text-ink-dim">
        {t('rss.oneshot.count', { count: items.length })} <Dot />{' '}
        <span className="value">{t(`rss.kind.${read.kind}`)}</span>
      </p>

      <WorkPicker
        // 送出中不換作品與 Route：送的是按下那一刻的那一組，畫面上的資料夾名要跟它一致。
        locked={send.isPending}
        seed={searchTerm(items[0].title)}
        work={work}
        onWork={onWork}
        media={media}
        mediaFailed={mediaFailed}
        route={route}
        onRoute={onRoute}
      />

      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-2">
        <p id={listId} className="label text-ink-dim">
          {t('rss.oneshot.list')}
        </p>
        {all.size > 0 && (
          <GhostButton
            type="button"
            disabled={send.isPending}
            onClick={() => setPicked(allPicked ? new Set() : all)}
          >
            {allPicked ? t('rss.oneshot.pickNone') : t('rss.oneshot.pickAll', { count: all.size })}
          </GhostButton>
        )}
      </div>
      <ul aria-labelledby={listId} className="grid gap-px bg-rule">
        {items.map((row) => (
          <li key={row.guid} className="min-w-0 bg-well px-4 py-2.5">
            <Row
              row={row}
              checked={picked.has(row.guid)}
              locked={send.isPending}
              outcome={outcomes.get(row.guid)}
              onToggle={(on) => toggle(row.guid, on)}
            />
          </li>
        ))}
      </ul>

      {send.isError && (
        <Notice signal="blocked" label={t('common.failed')}>
          {t('rss.oneshot.stopped', { done: progress })}
        </Notice>
      )}
      {send.data && (
        <p role="status" className="text-sm text-ink">
          {t('rss.oneshot.done', send.data)}
        </p>
      )}

      <div className={STICKY_ACTION}>
        <div className="grid gap-2 sm:max-w-md">
          {media && route !== null ? (
            <>
              <p className="max-w-prose text-xs text-ink">
                {media.folder_frozen ? t('rss.bind.alreadyFrozen') : t('rss.oneshot.willFreeze')}
              </p>
              {/* 資料夾名是機器字串，會原樣出現在檔案系統上（同 `SubmitAction`）。 */}
              <p className="value text-xs wrap-anywhere text-ink">{media.folder_name || '—'}</p>
              <PrimaryButton
                type="button"
                busy={send.isPending}
                disabled={order.length === 0}
                onClick={() => send.mutate()}
              >
                {send.isPending
                  ? t('rss.oneshot.sending', { done: progress, total: order.length })
                  : order.length === 0
                    ? t('rss.oneshot.pickFirst')
                    : t('rss.oneshot.send', { count: order.length })}
              </PrimaryButton>
            </>
          ) : (
            <p className="max-w-prose text-xs text-ink-dim">{t('rss.oneshot.needWork')}</p>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * 送到哪一部作品、哪一條 Route。搜尋框預填從第一筆的發佈名讀出的作品名（同待綁定那一列的綁定）。
 */
function WorkPicker({
  locked,
  seed,
  work,
  onWork,
  media,
  mediaFailed,
  route,
  onRoute,
}: {
  locked: boolean
  seed: string
  work: Pickable | null
  onWork: (work: Pickable) => void
  media: Media | undefined
  mediaFailed: boolean
  route: number | null
  onRoute: (route: number | null) => void
}) {
  const { t, i18n } = useTranslation()
  const [query, setQuery] = useState(seed)
  const debounced = useDebounced(query.trim(), SEARCH_DEBOUNCE_MS)
  const found = useQuery({
    ...searchQueryOptions(debounced),
    enabled: debounced.length >= MIN_QUERY_LENGTH,
  })
  const titleOf = (item: Pickable) =>
    displayRound(i18n.language, { 'zh-Hant': item.title, en: item.title_en }) || item.title_en
  const aboutOf = (item: Pickable) =>
    [item.year, t(`rss.bind.kind.${item.kind}`)].filter(Boolean).join(' · ')
  const results = found.data?.items ?? []

  return (
    // `fieldset disabled` 一次鎖住裡面的每一個控制項（搜尋框、作品鍵、Route 下拉）。
    <fieldset disabled={locked} className="grid gap-3 border-2 border-rule bg-well px-4 py-3">
      <legend className="sr-only">{t('rss.oneshot.work')}</legend>
      <p aria-hidden="true" className="label text-ink-dim">
        {t('rss.oneshot.work')}
      </p>
      <Field
        label={t('rss.bind.search')}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {found.isFetching && <p className="text-xs text-ink-dim">{t('rss.bind.searching')}</p>}
      {found.data?.problem ? (
        <p role="alert" className="max-w-prose text-xs text-blocked-ink">
          {t('rss.bind.off')}
        </p>
      ) : found.data && results.length === 0 ? (
        <p className="text-xs text-ink-dim">{t('rss.bind.none')}</p>
      ) : null}
      {results.length > 0 && (
        <Choices
          label={t('rss.bind.results')}
          items={results.slice(0, 8)}
          picked={work}
          onPick={onWork}
          titleOf={titleOf}
          aboutOf={aboutOf}
        />
      )}
      {work !== null && !media && !mediaFailed && (
        <p className="text-xs text-ink-dim">{t('rss.bind.reading')}</p>
      )}
      {mediaFailed && (
        <p role="alert" className="max-w-prose text-xs text-blocked-ink">
          {t('rss.bind.mediaOff')}
        </p>
      )}
      {media && <RoutePicker media={media} value={route} onChange={onRoute} />}
    </fieldset>
  )
}

/** 清單的一列：勾選格、發佈名，下面一行解析結果，再下面是「已經有了」與送出之後的結果。 */
function Row({
  row,
  checked,
  locked,
  outcome,
  onToggle,
}: {
  row: OneshotItem
  checked: boolean
  locked: boolean
  outcome: Outcome | undefined
  onToggle: (on: boolean) => void
}) {
  const { t, i18n } = useTranslation()
  const id = useId()
  const factsId = `${id}-facts`
  const { code, noteKey } = estimate(row)
  const tokens = tagTokens(row.tags)
  const done = outcome !== undefined && outcome.kind !== 'refused'

  return (
    <div className="grid min-w-0 gap-1">
      <div className="flex items-start gap-3">
        <input
          id={id}
          type="checkbox"
          aria-describedby={factsId}
          checked={checked}
          disabled={locked || done}
          onChange={(event) => onToggle(event.target.checked)}
          className="mt-0.5 size-4 shrink-0 accent-[var(--color-assigned)] disabled:cursor-not-allowed"
        />
        <label htmlFor={id} className="value min-w-0 text-sm wrap-anywhere text-ink">
          {row.title}
        </label>
      </div>
      <p id={factsId} className="pl-7 text-xs text-ink-dim">
        {/* 合集、區間只標示、不擋（排除條件只管自動下載，brief §15）：中性色塊，不塗漆。 */}
        {row.release_kind !== 'single' && (
          <>
            <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.neutral}`}>
              {t(`rss.oneshot.kind.${row.release_kind}`)}
            </span>{' '}
          </>
        )}
        <span className="value">{[code, noteKey ? t(noteKey) : ''].filter(Boolean).join(' ')}</span>
        {tokens.length > 0 && (
          <>
            {' '}
            <Dot /> <span className="value">{tokens.join(' · ')}</span>
          </>
        )}
        {row.published_at && (
          <>
            {' '}
            <Dot /> {t('rss.items.published')}{' '}
            <span className="value">{whenText(row.published_at, i18n.language)}</span>
          </>
        )}
        {row.size !== null && (
          <>
            {' '}
            <Dot /> <span className="value">{formatSize(row.size, i18n.language)}</span>
          </>
        )}
      </p>
      {row.job_hash && outcome === undefined && (
        <p className="pl-7 text-xs text-ink-dim">
          {t('rss.oneshot.hasJob')} <JobLink hash={row.job_hash}>{t('rss.items.job')}</JobLink>
        </p>
      )}
      {row.known !== null && (
        <p className="pl-7 text-xs wrap-anywhere text-ink-dim">
          {t('rss.oneshot.known', { known: row.known })}
        </p>
      )}
      {outcome && <Result outcome={outcome} />}
    </div>
  )
}

function Result({ outcome }: { outcome: Outcome }) {
  const { t } = useTranslation()
  if (outcome.kind === 'refused') {
    return (
      <div className="grid gap-1 pl-7">
        <p className="max-w-prose text-xs text-blocked-ink">
          {t(`jobs.refusal.${outcome.reason}`)}
        </p>
        {/* `job_removed` 的 `detail` 是那一筆的 hash：下一步在它的詳情頁上（同 `SubmitAction`）。 */}
        {outcome.reason === 'job_removed' ? (
          <p className="text-xs">
            <JobLink hash={outcome.detail}>{t('submit.toRemovedJob')}</JobLink>
          </p>
        ) : (
          outcome.detail && (
            <p className="value text-xs wrap-anywhere text-ink-dim">{outcome.detail}</p>
          )
        )}
      </div>
    )
  }
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 pl-7 text-xs">
      <span className={`label px-1.5 py-0.5 ${SIGNAL_FILL.secured}`}>
        {t(`rss.oneshot.outcome.${outcome.kind}`)}
      </span>
      <JobLink hash={outcome.hash}>{t('rss.items.job')}</JobLink>
    </p>
  )
}
