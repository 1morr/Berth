import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { MIN_QUERY_LENGTH, searchQueryOptions, type DiscoverItem } from '../api/discover'
import { mediaQueryOptions, type Media } from '../api/media'
import { bindSeries, parseRssRefusal, RSS_KEY, type Candidate, type RssSeries } from '../api/rss'
import { ConfirmPanel } from '../components/ConfirmPanel'
import {
  Checkbox,
  CONFIRM_ACTIONS,
  Field,
  GhostButton,
  Notice,
  PrimaryButton,
} from '../components/controls'
import { SEARCH_DEBOUNCE_MS, useDebounced } from '../components/useDebounced'
import { useInPlaceConfirm } from '../components/useInPlaceConfirm'
import { displayRound } from '../i18n/displayRound'
import { RoutePicker } from '../media/RoutePicker'
import { searchTerm } from './searchTerm'

/**
 * 待綁定那一列的「綁定」（`.scratch/m3/rss-shape.md` §3）：就地展開，不是 dialog。
 *
 * 搜作品（探索頁同一支 `/discover/search`，搜尋框預填從發佈名讀出的作品名）→ 挑一部 → 讀它的
 * 詳情（`GET /media/{id}` 讓那一列長出來，資料夾名與收得下它的 Route 都在裡面）→ 挑 Route →
 * 確認區塊重述**資料夾名**與「將送出 N 集」。資料夾名在綁定那一刻定死（plan §2.2），之後的送單
 * 沒有人按，所以按下去之前要讓人看到那一串（DESIGN.md 的 The Focus Follows The Confirm Rule 的
 * 最後一句：確認裡要重述會被寫死的東西）。
 *
 * 送單被拒不讓綁定失敗（Route 紅燈、磁碟門檻）：綁好之後那幾筆留在 Feed Item 清單上帶著原文。
 *
 * **候選**（票 09）：自動綁定認出來、留給人選的作品（同名不同年、兩部都對得上、Route 不只一條）。
 * 收起時每一部一顆鍵，按一下就展開並選定它——跳過搜尋，直接到 Route 與確認；展開後它們排在搜尋
 * 框上面，選定的那一顆是按下的樣子。確認照舊要按：資料夾名在那一刻定死。
 *
 * **補舊集**（票 12）：Mikan 的 RSS Series 多一格「同時補下載舊集」，預設勾選（brief §15）——綁定時
 * 讀這個字幕組的單一 feed，聚合 feed 沒帶到的集數一起送。幾集要讀了才知道，所以勾著時確認鍵不說
 * 總數，只說「並補舊集」；取消勾選時那幾集記成略過，之後的每日補漏也不送它們。
 */
export function SeriesBinder({
  series,
  onDone,
}: {
  series: RssSeries
  /** 綁成之後這一列會離開待綁定段，這一句給看不見畫面的人。 */
  onDone: (said: string) => void
}) {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const { asked, open, close, trigger, panel, onKeyDown } = useInPlaceConfirm()
  const [query, setQuery] = useState(() => searchTerm(series.title_raw))
  const [picked, setPicked] = useState<Pickable | null>(null)
  // `undefined` 是「還沒選過」：那時用預選（`preselect`）；選了「不選」是 `null`。
  const [chosen, setChosen] = useState<number | null | undefined>(undefined)
  const [backfill, setBackfill] = useState(true)
  // 只有 Mikan 有單一 feed（番組 × 字幕組）；其他來源的新 Feed 第一輪就帶著歷史（票 11 的預覽）。
  const mikan = series.mikan_bangumi_id !== null
  const backfilling = mikan && backfill
  const search = useRef<HTMLInputElement>(null)
  const headingId = useId()
  const debounced = useDebounced(query.trim(), SEARCH_DEBOUNCE_MS)
  const found = useQuery({
    ...searchQueryOptions(debounced),
    enabled: asked && debounced.length >= MIN_QUERY_LENGTH,
  })
  const media = useQuery({ ...mediaQueryOptions(picked?.id ?? ''), enabled: picked !== null })
  const bind = useMutation({
    mutationFn: () => {
      if (picked === null || route === null) throw new Error('nothing picked')
      return bindSeries(series.id, picked.id, route, backfilling)
    },
    onSuccess: async (bound) => {
      close()
      onDone(t('rss.bind.done', { count: bound.submitted }))
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: RSS_KEY }),
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
        // 資料夾名定了、這部作品變成 tracked：詳情頁那兩格要跟著換（M3 票 06 的同一條）。
        queryClient.invalidateQueries({ queryKey: ['media'] }),
      ])
    },
  })

  // 排在 `useInPlaceConfirm` 之後：它先把焦點給整個確認區塊，這裡再送進搜尋框（同 `WorkPicker`）。
  useEffect(() => {
    if (asked) search.current?.focus()
  }, [asked])

  const detail = media.data
  const route = chosen === undefined ? preselect(detail) : chosen
  const candidates = series.candidates
  const pick = (item: Pickable) => {
    setPicked(item)
    setChosen(undefined)
  }
  const titleOf = (item: Pickable) =>
    displayRound(i18n.language, { 'zh-Hant': item.title, en: item.title_en }) || item.title_en
  const aboutOf = (item: Pickable) =>
    [item.year, t(`rss.bind.kind.${item.kind}`)].filter(Boolean).join(' · ')

  if (!asked) {
    return (
      <>
        {candidates.map((item) => (
          <GhostButton
            key={item.id}
            type="button"
            onClick={() => {
              pick(item)
              open()
            }}
          >
            {/* 動詞寫在鍵上：只有片名的話看不出按下去會做什麼。 */}
            {t('rss.bind.pick', { title: titleOf(item) })}
            <span className="ml-2 text-xs text-ink-dim">{aboutOf(item)}</span>
          </GhostButton>
        ))}
        <GhostButton ref={trigger} type="button" onClick={open}>
          {t('rss.bind.start')}
        </GhostButton>
      </>
    )
  }

  // 候選已經列在上面了，搜尋結果裡的同一部不再列一次。
  const items = (found.data?.items ?? []).filter(
    (item) => !candidates.some((one) => one.id === item.id),
  )
  const refusal = bind.isError ? parseRssRefusal(bind.error) : null

  return (
    <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={headingId}>
      <p id={headingId} className="label text-ink-dim">
        {t('rss.bind.label')}
      </p>
      {candidates.length > 0 && (
        <Choices
          label={t('rss.bind.candidates')}
          items={candidates}
          picked={picked}
          onPick={pick}
          titleOf={titleOf}
          aboutOf={aboutOf}
        />
      )}
      <Field
        ref={search}
        label={t('rss.bind.search')}
        type="search"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setPicked(null)
          setChosen(undefined)
        }}
      />
      {found.isFetching && <p className="text-xs text-ink-dim">{t('rss.bind.searching')}</p>}
      {found.data?.problem ? (
        <p role="alert" className="max-w-prose text-xs text-blocked-ink">
          {t('rss.bind.off')}
        </p>
      ) : found.data && found.data.items.length === 0 ? (
        <p className="text-xs text-ink-dim">{t('rss.bind.none')}</p>
      ) : null}
      {items.length > 0 && (
        <Choices
          label={t('rss.bind.results')}
          items={items.slice(0, 8)}
          picked={picked}
          onPick={pick}
          titleOf={titleOf}
          aboutOf={aboutOf}
        />
      )}

      {picked !== null && media.isPending && (
        <p className="text-xs text-ink-dim">{t('rss.bind.reading')}</p>
      )}
      {picked !== null && media.isError && (
        <p role="alert" className="max-w-prose text-xs text-blocked-ink">
          {t('rss.bind.mediaOff')}
        </p>
      )}
      {detail && (
        <div className="grid gap-3">
          <RoutePicker media={detail} value={route} onChange={setChosen} />
          <div className="grid gap-1">
            <p className="max-w-prose text-xs text-ink">
              {detail.folder_frozen ? t('rss.bind.alreadyFrozen') : t('rss.bind.willFreeze')}
            </p>
            {/* 資料夾名是機器字串——它會原樣出現在檔案系統上，所以走 `.value`（同 `SubmitAction`）。 */}
            <p className="value text-xs wrap-anywhere text-ink">{detail.folder_name || '—'}</p>
            <p className="max-w-prose text-xs text-ink-dim">
              {t('rss.bind.willSend', { count: series.waiting })}
            </p>
          </div>
          {mikan && (
            <Checkbox
              label={t('rss.bind.backfill')}
              hint={t(backfill ? 'rss.bind.backfillOn' : 'rss.bind.backfillOff')}
              checked={backfill}
              onChange={setBackfill}
            />
          )}
        </div>
      )}

      <div className={CONFIRM_ACTIONS}>
        {detail && route !== null ? (
          <PrimaryButton type="button" busy={bind.isPending} onClick={() => bind.mutate()}>
            {bind.isPending
              ? t('rss.bind.binding')
              : t(backfilling ? 'rss.bind.confirmBackfill' : 'rss.bind.confirm', {
                  count: series.waiting,
                })}
          </PrimaryButton>
        ) : (
          <span />
        )}
        <GhostButton type="button" onClick={close}>
          {t('common.cancel')}
        </GhostButton>
      </div>

      {bind.isError && (
        <Notice signal="blocked" label={t('common.failed')}>
          {refusal ? t(`rss.refusal.${refusal.reason}`) : t('rss.failed')}
          {refusal?.detail ? <span className="value block text-xs">{refusal.detail}</span> : null}
        </Notice>
      )}
    </ConfirmPanel>
  )
}

/** 選得了的一部作品：搜尋結果（`DiscoverItem`）與自動綁定的候選（`Candidate`）共有的那幾格。 */
type Pickable = Pick<DiscoverItem | Candidate, 'id' | 'kind' | 'title' | 'title_en' | 'year'>

/** 一串可選的作品，一部一顆鍵；選定的那一顆是按下的樣子。 */
function Choices({
  label,
  items,
  picked,
  onPick,
  titleOf,
  aboutOf,
}: {
  label: string
  items: readonly Pickable[]
  picked: Pickable | null
  onPick: (item: Pickable) => void
  titleOf: (item: Pickable) => string
  aboutOf: (item: Pickable) => string
}) {
  const labelId = useId()
  return (
    <div className="grid gap-1">
      <p id={labelId} className="label text-ink-dim">
        {label}
      </p>
      <ul className="grid gap-1" aria-labelledby={labelId}>
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              aria-pressed={picked?.id === item.id}
              onClick={() => onPick(item)}
              className={`value flex min-h-6 w-full flex-wrap items-baseline gap-x-2 border-2 px-3 py-2 text-left text-sm text-ink ${
                picked?.id === item.id
                  ? 'border-rule-strong bg-deck'
                  : 'border-rule hover:border-rule-strong'
              }`}
            >
              <span className="wrap-anywhere">{titleOf(item)}</span>
              <span className="text-xs text-ink-dim">{aboutOf(item)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** 詳情一到就預選：上次用的 Route，沒有就是唯一的那一條。兩條以上而從沒送過單時留給人選。 */
function preselect(detail: Media | undefined): number | null {
  if (!detail) return null
  const choices = detail.routes.map((row) => row.id)
  if (detail.default_route_id !== null && choices.includes(detail.default_route_id))
    return detail.default_route_id
  return choices.length === 1 ? choices[0] : null
}
