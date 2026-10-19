import { useQuery } from '@tanstack/react-query'
import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'

import { MIN_QUERY_LENGTH, searchQueryOptions } from '../api/discover'
import { mediaQueryOptions, type Media } from '../api/media'
import { oneshotQueryOptions, parseRssRefusal } from '../api/rss'
import { Field, PrimaryButton } from '../components/controls'
import { RequestFailed } from '../components/RequestFailed'
import { problemText } from '../components/requestProblem'
import { SEARCH_DEBOUNCE_MS, useDebounced } from '../components/useDebounced'
import { displayRound } from '../i18n/displayRound'
import { RoutePicker } from '../media/RoutePicker'
import { SectionHeading } from '../components/SectionHeading'
import { OneshotList } from './OneshotList'
import { preselect } from './preselect'
import { Choices, type Pickable } from './WorkChoices'

/**
 * 一次性 RSS 連結（brief §15、M3 票 18）：貼一條網址 → 讀一次 → 挑作品與 Route → 勾幾筆 → 送出。
 *
 * **不建 Feed**：讀是 `POST /rss/oneshot`（只讀）；清單、勾選與送出是共用的 `OneshotList`（作品頁的
 * 「只下載現有的」也用它，M4 票 112）。
 *
 * **作品排在清單前面**：選了之後清單換成照那部作品換算的季集，並標出帳本已經有的那幾筆——勾之前就
 * 看得到哪幾集不必再下。
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
      ? problemText(t, read.error, t('request.notDone'))
      : undefined

  const seed = read.data?.items[0]?.search_term ?? ''

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
        <OneshotList
          // 換一條網址就是另一批：勾選與結果從頭來。
          key={url}
          read={read.data}
          media={media}
          route={route}
          picker={(locked) => (
            <WorkPicker
              // 送出中不換作品與 Route：送的是按下那一刻的那一組，畫面上的資料夾名要跟它一致。
              locked={locked}
              seed={seed}
              work={work}
              onWork={(next) => {
                setWork(next)
                setChosen(undefined)
              }}
              media={media}
              mediaError={work !== null && detail.isError ? detail.error : null}
              route={route}
              onRoute={setChosen}
            />
          )}
        />
      )}
    </section>
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
  mediaError,
  route,
  onRoute,
}: {
  locked: boolean
  seed: string
  work: Pickable | null
  onWork: (work: Pickable) => void
  media: Media | undefined
  /** 讀作品詳情的失敗（`null` 表示沒失敗）。 */
  mediaError: unknown
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
      {found.isError ? (
        <RequestFailed error={found.error} lead={t('rss.bind.searchFailed')} />
      ) : found.data?.problem ? (
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
      {work !== null && !media && mediaError === null && (
        <p className="text-xs text-ink-dim">{t('rss.bind.reading')}</p>
      )}
      {mediaError !== null && (
        <RequestFailed error={mediaError} lead={t('rss.bind.mediaReadFailed')} />
      )}
      {media && <RoutePicker media={media} value={route} onChange={onRoute} />}
    </fieldset>
  )
}
