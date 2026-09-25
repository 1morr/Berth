import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { MIN_QUERY_LENGTH, searchQueryOptions, type DiscoverItem } from '../api/discover'
import { mediaQueryOptions, type Media } from '../api/media'
import { bindSeries, parseRssRefusal, RSS_KEY, type RssSeries } from '../api/rss'
import { ConfirmPanel } from '../components/ConfirmPanel'
import { CONFIRM_ACTIONS, Field, GhostButton, Notice, PrimaryButton } from '../components/controls'
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
  const [picked, setPicked] = useState<DiscoverItem | null>(null)
  // `undefined` 是「還沒選過」：那時用預選（`preselect`）；選了「不選」是 `null`。
  const [chosen, setChosen] = useState<number | null | undefined>(undefined)
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
      return bindSeries(series.id, picked.id, route)
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

  if (!asked) {
    return (
      <GhostButton ref={trigger} type="button" onClick={open}>
        {t('rss.bind.start')}
      </GhostButton>
    )
  }

  const titleOf = (item: DiscoverItem) =>
    displayRound(i18n.language, { 'zh-Hant': item.title, en: item.title_en }) || item.title_en
  const items = found.data?.items ?? []
  const refusal = bind.isError ? parseRssRefusal(bind.error) : null

  return (
    <ConfirmPanel panelRef={panel} onKeyDown={onKeyDown} labelledBy={headingId}>
      <p id={headingId} className="label text-ink-dim">
        {t('rss.bind.label')}
      </p>
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
      ) : found.data && items.length === 0 ? (
        <p className="text-xs text-ink-dim">{t('rss.bind.none')}</p>
      ) : null}
      {items.length > 0 && (
        <ul className="grid gap-1" aria-label={t('rss.bind.results')}>
          {items.slice(0, 8).map((item) => (
            <li key={item.id}>
              <button
                type="button"
                aria-pressed={picked?.id === item.id}
                onClick={() => {
                  setPicked(item)
                  setChosen(undefined)
                }}
                className={`value flex min-h-6 w-full flex-wrap items-baseline gap-x-2 border-2 px-3 py-2 text-left text-sm text-ink ${
                  picked?.id === item.id
                    ? 'border-rule-strong bg-deck'
                    : 'border-rule hover:border-rule-strong'
                }`}
              >
                <span className="wrap-anywhere">{titleOf(item)}</span>
                <span className="text-xs text-ink-dim">
                  {[item.year, t(`rss.bind.kind.${item.kind}`)].filter(Boolean).join(' · ')}
                </span>
              </button>
            </li>
          ))}
        </ul>
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
        </div>
      )}

      <div className={CONFIRM_ACTIONS}>
        {detail && route !== null ? (
          <PrimaryButton type="button" busy={bind.isPending} onClick={() => bind.mutate()}>
            {bind.isPending
              ? t('rss.bind.binding')
              : t('rss.bind.confirm', { count: series.waiting })}
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

/** 詳情一到就預選：上次用的 Route，沒有就是唯一的那一條。兩條以上而從沒送過單時留給人選。 */
function preselect(detail: Media | undefined): number | null {
  if (!detail) return null
  const choices = detail.routes.map((row) => row.id)
  if (detail.default_route_id !== null && choices.includes(detail.default_route_id))
    return detail.default_route_id
  return choices.length === 1 ? choices[0] : null
}
